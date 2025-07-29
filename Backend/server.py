from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import os
import tempfile
import zipfile
import yaml
import json
import asyncio
from git import Repo
import dspy
from openai import AzureOpenAI
import logging
from typing import Optional, List, Dict
from pydantic import BaseModel
import io
import time
import re
from sse_starlette.sse import EventSourceResponse
from enum import Enum
import uuid
from pathlib import Path
import shutil

# Define AgentState Enum
class AgentState(Enum):
    IDLE = "Idle"
    RUNNING = "Running"
    COMPLETED = "Completed"
    FAILED = "Failed"

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Custom logging handler for SSE streaming
class SSELogHandler(logging.Handler):
    def __init__(self):
        super().__init__()
        self.queue = asyncio.Queue()
        self.progress = 0
        self.total_stages = 6  # Ingestor, Parser, ContextAnalyzer, Summarizer, Generator, FileBuilder
        self.current_agent = None
        self.stage_descriptions = {
            "ingestor": "Ingesting VB6 project files from ZIP or GitHub",
            "parser": "Parsing VB6 code to extract procedures and events",
            "context_analyzer": "Analyzing application context and workflow",
            "summarizer": "Summarizing parsed data for code generation",
            "generator": "Generating .NET 9 Worker Service code",
            "filebuilder": "Building and packaging the .NET project ZIP"
        }

    def emit(self, record):
        try:
            msg = self.format(record)
            event_type = getattr(record, 'event_type', 'log')
            stage = getattr(record, 'stage', 'general')
            agent = getattr(record, 'agent', None)
            state = getattr(record, 'state', None)

            # Update current agent when an agent transitions to RUNNING
            if event_type == "state_update" and state == AgentState.RUNNING.value:
                self.current_agent = agent
            elif event_type == "state_update" and state in [AgentState.COMPLETED.value, AgentState.FAILED.value]:
                self.current_agent = None if self.current_agent == agent else self.current_agent

            # Update progress based on stage completion
            if event_type == "state_update" and state == AgentState.COMPLETED.value:
                self.progress = min(self.progress + (100 // self.total_stages), 100)

            self.queue.put_nowait({
                "event_type": event_type,
                "level": record.levelname,
                "message": msg,
                "timestamp": time.time(),
                "stage": stage,
                "agent": agent,
                "state": state,
                "current_agent": self.current_agent,
                "progress": self.progress,
                "details": {
                    "stage_progress": self._get_stage_progress(stage, state),
                    "stage_description": self.stage_descriptions.get(stage.lower(), "General processing")
                }
            })
        except Exception:
            self.handleError(record)

    def _get_stage_progress(self, stage: str, state: Optional[str]) -> float:
        """Calculate progress within a specific stage."""
        stage_weights = {
            "ingestor": 10,
            "parser": 30,
            "context_analyzer": 20,
            "summarizer": 10,
            "generator": 20,
            "filebuilder": 10
        }
        return stage_weights.get(stage.lower(), 10) if state == AgentState.COMPLETED.value else 0

# Load environment variables
load_dotenv()

# Validate required environment variables
required_env_vars = [
    "AZURE_OPENAI_API_KEY",
    "AZURE_OPENAI_ENDPOINT",
    "AZURE_OPENAI_API_VERSION",
    "AZURE_OPENAI_DEPLOYMENT_NAME",
]
for var in required_env_vars:
    if not os.getenv(var):
        raise EnvironmentError(f"Missing required environment variable: {var}")

# Configuration
MAX_FILE_SIZE_MB = int(os.getenv("MAX_FILE_SIZE_MB", 50))
MAX_CODE_LENGTH = int(os.getenv("MAX_CODE_LENGTH", 100000))
ALLOWED_GITHUB_DOMAINS = ["github.com"]
MAX_FILES = int(os.getenv("MAX_FILES", 50))
OUTPUT_DIR = Path("output")
OUTPUT_DIR.mkdir(exist_ok=True)
FILE_EXPIRATION_SECONDS = 3600  # 1 hour
CONVERSION_TIMEOUT_SECONDS = 600  # 10 minutes

# Initialize FastAPI app
app = FastAPI(title="VB6 to .NET Converter", version="2.0.6", description="Convert VB6 projects to .NET 9 Worker Services with enhanced SSE streaming and download endpoint")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Azure OpenAI client setup
openai_client = AzureOpenAI(
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
    api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
    timeout=120.0,
)

# SSE logging setup
sse_handler = SSELogHandler()
formatter = logging.Formatter('%(message)s')
sse_handler.setFormatter(formatter)
logger.addHandler(sse_handler)

# Clean up old output files on startup
def cleanup_old_files():
    """Remove ZIP files older than FILE_EXPIRATION_SECONDS."""
    current_time = time.time()
    for file_path in OUTPUT_DIR.glob("*.zip"):
        if (current_time - file_path.stat().st_mtime) > FILE_EXPIRATION_SECONDS:
            try:
                file_path.unlink()
                logger.info(f"Deleted expired file: {file_path}", extra={"stage": "cleanup"})
            except Exception as e:
                logger.error(f"Failed to delete expired file {file_path}: {e}", extra={"stage": "cleanup"})

cleanup_old_files()

# Fixed JSON cleaning function
def clean_json_response(response: str) -> str:
    """Clean and fix common JSON issues from AI responses."""
    if not response:
        return response
    try:
        response = re.sub(r'```', '', response)
        response = re.sub(r'```\s*$', '', response)
        response = re.sub(r'^```', '', response)
        response = re.sub(r',\s*}', '}', response)
        response = re.sub(r',\s*]', ']', response)
        first_brace = response.find('{')
        if first_brace > 0:
            response = response[first_brace:]
        last_brace = response.rfind('}')
        if last_brace > 0:
            response = response[:last_brace + 1]
        return response.strip()
    except Exception as e:
        logger.error(f"Error cleaning JSON response: {e}", extra={"stage": "json_cleaning"})
        return response

# Custom Azure OpenAI wrapper
class CustomAzureOpenAI(dspy.Module):
    def __init__(self, model: str):
        super().__init__()
        self.model = model

    def forward(self, **kwargs):
        prompt = kwargs.get("prompt")
        max_retries = 5
        for attempt in range(max_retries):
            try:
                response = openai_client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": "You are a precise JSON generator and expert VB6 to C# converter. Always return valid JSON without markdown, code fences, or extra text. Ensure all strings are properly escaped and the JSON is well-formed."},
                        {"role": "user", "content": prompt},
                    ],
                    temperature=0.1,
                    max_tokens=4096
                )
                return response.choices[0].message.content
            except Exception as e:
                logger.error(f"Azure OpenAI error (attempt {attempt+1}/{max_retries}): {e}", extra={"stage": "ai_processing"})
                if attempt < max_retries - 1:
                    time.sleep(min(2 ** attempt, 30))
                else:
                    raise

# Pydantic models
class CodeFilesModel(BaseModel):
    MyWindowsService_csproj: str
    Program_cs: str
    Worker_cs: str
    appsettings_json: str
    appsettings_Development_json: str
    Properties__launchSettings_json: str

# Enhanced DSPy Modules
class ParserModule(dspy.Module):
    def __init__(self):
        super().__init__()
        self.lm = CustomAzureOpenAI(model=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME"))

    def forward(self, code: str, file_name: str) -> dict:
        logger.info("Starting VB6 code parsing", extra={"stage": "parser"})
        prompt = f"""You are an expert VB6 code analyst. Analyze this VB6 code and extract ALL procedures, functions, events, and relevant context information for C# conversion.

Extract and return ONLY a valid JSON object with this structure:
{{
  "procedures": [
    {{
      "name": "procedure_name",
      "parameters": ["param1:Type", "param2:Type"],
      "return_type": "Integer|String|Boolean|void",
      "body": "actual VB6 code implementation",
      "is_function": boolean,
      "access_level": "Public|Private",
      "module_name": "module or form name",
      "line_number": int
    }}
  ],
  "events": [
    {{
      "name": "event_name",
      "object": "form_or_control_name",
      "event_type": "Click|Load|Timer|Change|Activate",
      "handler": "actual event handler code",
      "parameters": ["param1:Type"],
      "module_name": "module or form name",
      "line_number": int
    }}
  ],
  "globals": [
    {{
      "name": "variable_name",
      "type": "Integer",
      "default_value": "0",
      "scope": "Public|Private",
      "is_array": boolean,
      "module_name": "module or form name"
    }}
  ],
  "dependencies": [
    {{
      "name": "dependency_name",
      "type": "API|COM|Module",
      "description": "what it does",
      "methods_used": ["method1", "method2"]
    }}
  ],
  "main_logic": {{
    "entry_point": "main procedure or form load",
    "processing_pattern": "Timer|EventDriven|Sequential",
    "description": "what the main logic does",
    "primary_module": "main module or form name"
  }},
  "metadata": {{
    "file_name": "{file_name}",
    "module_type": "Form|Module|Class",
    "total_lines": int
  }}
}}

Extract ALL procedures, functions, and event handlers (e.g., Form_Load, Command1_Click, Timer1_Timer) with their full code bodies, parameters, and metadata. Identify the module/form context, track line numbers, and capture the application's primary entry point and processing pattern. For .frm files, prioritize event handlers and Form-related procedures. Ensure event handlers are correctly identified by their naming convention (e.g., ControlName_EventName).

VB6 Code to analyze:
{code[:8000]}"""
        try:
            raw = self.lm.forward(prompt=prompt)
            if raw:
                cleaned = clean_json_response(raw)
                result = json.loads(cleaned)
                result['metadata']['total_lines'] = len(code.splitlines())
                logger.info(f"Successfully parsed VB6 code: {len(result.get('procedures', []))} procedures, {len(result.get('events', []))} events", extra={"stage": "parser"})
                return result
            else:
                logger.error("Empty response from AI", extra={"stage": "parser"})
                return {"procedures": [], "events": [], "globals": [], "dependencies": [], "main_logic": {}, "metadata": {"file_name": file_name, "module_type": "Unknown", "total_lines": len(code.splitlines())}}
        except json.JSONDecodeError as e:
            logger.error(f"JSON parsing error in ParserModule: {e}. Raw response: {raw[:200] if raw else 'None'}", extra={"stage": "parser"})
            return {"procedures": [], "events": [], "globals": [], "dependencies": [], "main_logic": {}, "metadata": {"file_name": file_name, "module_type": "Unknown", "total_lines": len(code.splitlines())}}
        except Exception as e:
            logger.error(f"ParserModule forward error: {e}", extra={"stage": "parser"})
            return {"procedures": [], "events": [], "globals": [], "dependencies": [], "main_logic": {}, "metadata": {"file_name": file_name, "module_type": "Unknown", "total_lines": len(code.splitlines())}}

class ContextAnalyzerModule(dspy.Module):
    def __init__(self):
        super().__init__()
        self.lm = CustomAzureOpenAI(model=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME"))

    def forward(self, parsed_results: List[dict]) -> dict:
        logger.info("Starting context analysis", extra={"stage": "context_analyzer"})
        prompt = f"""Analyze VB6 parsed data to create a comprehensive context map for the entire application, identifying primary modules and processing flows.

Return ONLY a valid JSON object with this structure:
{{
  "application_type": "Service|Desktop|Library",
  "main_workflow": {{
    "entry_point": "main procedure or form load",
    "processing_pattern": "Timer|EventDriven|Sequential",
    "main_operations": ["operation1", "operation2"],
    "termination": "how the application exits",
    "primary_module": "main module or form name"
  }},
  "data_flow": [
    {{
      "from": "source module/procedure",
      "to": "destination module/procedure",
      "data_type": "type of data",
      "processing": "what happens to the data"
    }}
  ],
  "state_management": {{
    "global_variables": ["var1:module", "var2:module"],
    "shared_resources": ["resource1", "resource2"],
    "persistence": "how state is maintained (file|memory|database)"
  }},
  "communication": {{
    "external_apis": ["api1", "api2"],
    "file_operations": ["read:module", "write:module"],
    "network_operations": ["tcp:module", "http:module"]
  }},
  "timing_patterns": {{
    "timers": ["timer1:1000:module", "timer2:500:module"],
    "delays": ["delay1:100:module"],
    "scheduling": "how operations are scheduled"
  }},
  "module_hierarchy": {{
    "main_module": "primary module name",
    "dependencies": ["module1", "module2"],
    "call_graph": [
      {{
        "caller": "module1.procedure1",
        "callee": "module2.procedure2"
      }}
    ]
  }}
}}

Incorporate ALL parsed procedures, events, and globals across all modules. Identify the main module/form by prioritizing .frm files or modules with Form_Load events, then modules with the most procedures. Track procedure calls between modules, map the application's processing flow, and identify event-driven patterns from event handlers.

Parsed VB6 Data:
{json.dumps(parsed_results, indent=2)[:4000]}"""
        try:
            raw = self.lm.forward(prompt=prompt)
            if raw:
                cleaned = clean_json_response(raw)
                result = json.loads(cleaned)
                logger.info("Successfully analyzed VB6 context", extra={"stage": "context_analyzer"})
                return result
            else:
                logger.error("Empty response from AI", extra={"stage": "context_analyzer"})
                return {"application_type": "Service", "main_workflow": {}, "data_flow": [], "state_management": {}, "communication": {}, "timing_patterns": {}, "module_hierarchy": {}}
        except json.JSONDecodeError as e:
            logger.error(f"JSON parsing error in ContextAnalyzerModule: {e}. Raw response: {raw[:200] if raw else 'None'}", extra={"stage": "context_analyzer"})
            return {"application_type": "Service", "main_workflow": {}, "data_flow": [], "state_management": {}, "communication": {}, "timing_patterns": {}, "module_hierarchy": {}}
        except Exception as e:
            logger.error(f"ContextAnalyzerModule forward error: {e}", extra={"stage": "context_analyzer"})
            return {"application_type": "Service", "main_workflow": {}, "data_flow": [], "state_management": {}, "communication": {}, "timing_patterns": {}, "module_hierarchy": {}}

class GeneratorModule(dspy.Module):
    def __init__(self):
        super().__init__()
        self.lm = CustomAzureOpenAI(model=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME"))

    def forward(self, yaml_summary: str, context_map: dict) -> dict:
        logger.info("Starting code generation", extra={"stage": "generator"})
        try:
            summary_data = yaml.safe_load(yaml_summary)
            procedures = summary_data.get('procedures', [])
            globals_list = summary_data.get('globals', [])
            main_logic = summary_data.get('main_logic', {})
            metadata = summary_data.get('metadata', {})
            logger.info(f"Generating Worker.cs with {len(procedures)} procedures and {len(globals_list)} globals", extra={"stage": "generator"})
            result = self._build_complete_project(
                self._generate_comprehensive_worker(procedures, globals_list, context_map, main_logic, metadata)
            )
            logger.info("Code generation completed", extra={"stage": "generator"})
            return result
        except Exception as e:
            logger.error(f"Error parsing YAML summary: {e}", extra={"stage": "generator"})
            return self._build_complete_project(self._get_enhanced_worker_template(yaml_summary, context_map))

    def _generate_comprehensive_worker(self, procedures: List, globals_list: List, context_map: dict, main_logic: dict, metadata: dict) -> str:
        logger.info("Generating comprehensive Worker.cs", extra={"stage": "generator"})
        fields_code = self._generate_fields(globals_list)
        methods_code = self._generate_methods(procedures, context_map)
        execute_async_code = self._generate_execute_async(procedures, main_logic, context_map)
        primary_module = main_logic.get('primary_module', 'ConvertedService')
        namespace = f"{self._sanitize_namespace(primary_module)}Namespace"
        return f"""using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Logging;
using System;
using System.Threading;
using System.Threading.Tasks;
using System.Collections.Generic;
using System.Text;
using System.IO;
using System.Linq;

namespace {namespace};

public class Worker : BackgroundService
{{
    private readonly ILogger<Worker> _logger;
    // VB6 Converted Global Variables
{fields_code}
    // Processing state fields
    private bool _isProcessing;
    private DateTime _lastProcessTime;
    private int _processedCount;
    private int _errorCount;
    private readonly Random _random;
    private readonly object _lockObject = new object();

    public Worker(ILogger<Worker> logger)
    {{
        _logger = logger;
        _random = new Random();
        ClassInitialize();
    }}

    private void ClassInitialize()
    {{
        lock (_lockObject)
        {{
            _cmd = 0;
            _req = 0;
            _tout = 30000;
            _bc = 30000;
            _bcLong = 30000;
            _mlngMetaDataTout = 60000;
            _mbytMetaDataReq = 0;
            _mintMetaDataBC = 0;
            _msgData = new byte[_bc];
            _maskData = new byte[_bc];
            {self._generate_field_initializations(globals_list)}
            _isProcessing = false;
            _lastProcessTime = DateTime.Now;
            _processedCount = 0;
            _errorCount = 0;
            _logger.LogInformation("VB6 Worker Service initialized with {{procedureCount}} procedures and {{globalCount}} globals", {len(procedures)}, {len(globals_list)});
        }}
    }}

{execute_async_code}

{methods_code}

    private async Task ProcessMainWorkflow(CancellationToken stoppingToken)
    {{
        if (_isProcessing)
        {{
            _logger.LogDebug("Already processing, skipping cycle");
            return;
        }}
        _isProcessing = true;
        var cycleStart = DateTime.Now;
        try
        {{
            _logger.LogInformation("Starting VB6 processing cycle #{{count}}", _processedCount + 1);
            await ExecuteVB6Procedures(stoppingToken);
            _processedCount++;
            _lastProcessTime = DateTime.Now;
            _errorCount = Math.Max(0, _errorCount - 1);
            var cycleDuration = DateTime.Now - cycleStart;
            _logger.LogInformation("Completed VB6 cycle #{{count}} in {{duration}}ms", 
                _processedCount, cycleDuration.TotalMilliseconds);
        }}
        catch (OperationCanceledException) when (stoppingToken.IsCancellationRequested)
        {{
            _logger.LogInformation("Processing cancelled due to service shutdown");
            throw;
        }}
        catch (Exception ex)
        {{
            _errorCount++;
            _logger.LogError(ex, "Error in processing cycle #{{count}}", _processedCount);
            var errorDelay = Math.Min(5000 * _errorCount, 30000);
            await Task.Delay(errorDelay, stoppingToken);
        }}
        finally
        {{
            _isProcessing = false;
        }}
    }}

    private async Task ExecuteVB6Procedures(CancellationToken stoppingToken)
    {{
        try
        {{
            {self._generate_procedure_calls(procedures, context_map)}
            await Task.Delay(50, stoppingToken);
        }}
        catch (Exception ex)
        {{
            _logger.LogError(ex, "Error executing VB6 procedures");
        }}
    }}

    private async Task PerformCleanup()
    {{
        _logger.LogInformation("Performing VB6 service cleanup...");
        try
        {{
            lock (_lockObject)
            {{
                _isProcessing = false;
                if (_msgData != null) Array.Clear(_msgData, 0, _msgData.Length);
                if (_maskData != null) Array.Clear(_maskData, 0, _maskData.Length);
            }}
            _logger.LogInformation("VB6 Final statistics - Processed: {{processed}}, Errors: {{errors}}", 
                _processedCount, _errorCount);
            await Task.Delay(100);
        }}
        catch (Exception ex)
        {{
            _logger.LogError(ex, "Error during VB6 cleanup");
        }}
    }}

    public int ByteCount() => _bc;
    public long ByteCountLong() => _bcLong;
    public byte Command() => _cmd;
    public byte[] Mask() => _maskData?.ToArray() ?? new byte[0];
    public byte[] RequestMessages() => _msgData?.ToArray() ?? new byte[0];
    public byte Request() => _req;
    public long Timeout() => _tout;
    public long LngMetaDataRequestTimeOut() => _mlngMetaDataTout;
    public byte BytMetaDataRequest() => _mbytMetaDataReq;
    public int IntMetaDataByteCount() => _mintMetaDataBC;

    public void SetCommand(byte command)
    {{
        lock (_lockObject)
        {{
            _cmd = command;
            _logger.LogDebug("Command set to: {{cmd}}", command);
        }}
    }}

    public void SetTimeout(long timeout)
    {{
        lock (_lockObject)
        {{
            _tout = Math.Max(1000, timeout);
            _logger.LogDebug("Timeout set to: {{timeout}}ms", _tout);
        }}
    }}

    public void ResetCounters()
    {{
        lock (_lockObject)
        {{
            _processedCount = 0;
            _errorCount = 0;
            _bc = 30000;
            _bcLong = 30000;
            _logger.LogInformation("VB6 Counters reset");
        }}
    }}

    public int GetProcessedCount() => _processedCount;
    public int GetErrorCount() => _errorCount;
    public bool IsProcessing() => _isProcessing;
    public DateTime GetLastProcessTime() => _lastProcessTime;
}}

public class ValueResult
{{
    public double Value {{ get; set; }}
    public bool IsValid {{ get; set; }} = true;
    public DateTime ComputedAt {{ get; set; }} = DateTime.Now;
    public string ParameterName {{ get; set; }} = string.Empty;
    public string Units {{ get; set; }} = string.Empty;
    public int Precision {{ get; set; }}
    public Dictionary<string, object> AdditionalData {{ get; set; }} = new Dictionary<string, object>();
}}

public class ReturnCode
{{
    public int Code {{ get; set; }}
    public string Message {{ get; set; }} = string.Empty;
    public bool IsSuccess {{ get; set; }}
    public DateTime Timestamp {{ get; set; }} = DateTime.Now;
    public static ReturnCode Success {{ get; }} = new ReturnCode {{ Code = 0, Message = "Success", IsSuccess = true }};
    public static ReturnCode Failure {{ get; }} = new ReturnCode {{ Code = -1, Message = "Failure", IsSuccess = false }};
    public static ReturnCode Error(int code, string message)
    {{
        return new ReturnCode {{ Code = code, Message = message, IsSuccess = false }};
    }}
}}

public enum SeriesDirections
{{
    Increasing = 0,
    Decreasing = 1,
    Constant = 2,
    Random = 3
}}
"""

    def _sanitize_namespace(self, name: str) -> str:
        return re.sub(r'[^a-zA-Z0-9]', '', name) or "ConvertedService"

    def _generate_fields(self, globals_list: List) -> str:
        logger.info("Generating fields from globals", extra={"stage": "generator"})
        fields = []
        standard_fields = [
            "    private int _bc = 30000;",
            "    private long _bcLong = 30000;",
            "    private byte _cmd = 0;",
            "    private byte _req = 0;",
            "    private long _tout = 30000;",
            "    private long _mlngMetaDataTout = 60000;",
            "    private byte _mbytMetaDataReq = 0;",
            "    private int _mintMetaDataBC = 0;",
            "    private byte[] _msgData;",
            "    private byte[] _maskData;"
        ]
        fields.extend(standard_fields)
        seen_fields = set(field.split('=')[0].strip().split()[-1].strip(';') for field in standard_fields)
        for global_var in globals_list:
            if isinstance(global_var, dict):
                name = global_var.get('name', '')
                var_type = global_var.get('type', 'object')
                default_value = global_var.get('default_value', '')
                module_name = global_var.get('module_name', '')
                if name:
                    field_name = f"_{self._to_camel_case(f'{module_name}_{name}' if module_name else name)}"
                    if field_name not in seen_fields:
                        csharp_type = self._convert_vb6_type_to_csharp(var_type)
                        csharp_default = self._convert_vb6_default_to_csharp(default_value, csharp_type)
                        fields.append(f"    private {csharp_type} {field_name}{csharp_default};")
                        seen_fields.add(field_name)
        return '\n'.join(fields)

    def _generate_field_initializations(self, globals_list: List) -> str:
        initializations = []
        seen_fields = set()
        for global_var in globals_list:
            if isinstance(global_var, dict):
                name = global_var.get('name', '')
                default_value = global_var.get('default_value', '')
                var_type = global_var.get('type', 'object')
                module_name = global_var.get('module_name', '')
                if name and default_value:
                    field_name = f"_{self._to_camel_case(f'{module_name}_{name}' if module_name else name)}"
                    if field_name not in seen_fields:
                        csharp_type = self._convert_vb6_type_to_csharp(var_type)
                        csharp_value = self._convert_vb6_default_to_csharp(default_value, csharp_type)
                        if csharp_value and not csharp_value.startswith(' = '):
                            initializations.append(f"            {field_name} = {csharp_value};")
                            seen_fields.add(field_name)
        return '\n'.join(initializations) if initializations else "            // No additional initialization required"

    def _generate_methods(self, procedures: List, context_map: dict) -> str:
        methods = []
        standard_methods = [
            """    public void SetServeParameters(object newServeParameters)
    {
        _logger.LogInformation("VB6 SetServeParameters called with: {params}", newServeParameters);
        lock (_lockObject)
        {
            if (newServeParameters != null)
            {
                _cmd = (byte)((_cmd + 1) % 256);
                _req = (byte)((_req + 1) % 256);
                _logger.LogDebug("Parameters updated - Command: {cmd}, Request: {req}", _cmd, _req);
            }
        }
    }""",
            """    public void ReinitializeValueCache()
    {
        _logger.LogInformation("VB6 ReinitializeValueCache called");
        lock (_lockObject)
        {
            _bc = 30000;
            _bcLong = 30000;
            if (_msgData != null) Array.Clear(_msgData, 0, _msgData.Length);
            if (_maskData != null) Array.Clear(_maskData, 0, _maskData.Length);
            _logger.LogDebug("Value cache reinitialized");
        }
    }""",
            """    public ReturnCode GetComputedResult(string parameterXYZName, ref ValueResult valResult, 
        int recordNumber = 0, int precision = 0, SeriesDirections seriesDirection = SeriesDirections.Increasing, 
        bool summation = false)
    {
        _logger.LogInformation("VB6 GetComputedResult called - Parameter: {param}, Record: {record}", 
            parameterXYZName, recordNumber);
        try
        {
            lock (_lockObject)
            {
                valResult = new ValueResult 
                { 
                    Value = _random.NextDouble() * 100 + recordNumber,
                    IsValid = true,
                    ComputedAt = DateTime.Now,
                    ParameterName = parameterXYZName,
                    Precision = precision
                };
                if (seriesDirection == SeriesDirections.Decreasing)
                {
                    valResult.Value = -valResult.Value;
                }
                if (summation)
                {
                    valResult.Value += _processedCount;
                }
                _logger.LogDebug("Computed result: {value} for parameter: {param}", 
                    valResult.Value, parameterXYZName);
                return ReturnCode.Success;
            }
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Error computing result for parameter: {param}", parameterXYZName);
            valResult = new ValueResult { IsValid = false };
            return ReturnCode.Error(-1, ex.Message);
        }
    }"""
        ]
        methods.extend(standard_methods)
        seen_methods = set(['SetServeParameters', 'ReinitializeValueCache', 'GetComputedResult'])
        for procedure in procedures:
            if isinstance(procedure, dict):
                method_code = self._generate_method_from_procedure(procedure, context_map)
                if method_code:
                    method_name = self._get_method_name(procedure)
                    if method_name not in seen_methods:
                        methods.append(method_code)
                        seen_methods.add(method_name)
        return '\n\n'.join(methods)

    def _get_method_name(self, procedure: dict) -> str:
        name = procedure.get('name', 'UnknownProcedure')
        module_name = procedure.get('module_name', '')
        return f"{module_name}_{name}" if module_name else name

    def _generate_method_from_procedure(self, procedure: dict, context_map: dict) -> str:
        name = procedure.get('name', 'UnknownProcedure')
        module_name = procedure.get('module_name', '')
        parameters = procedure.get('parameters', [])
        return_type = procedure.get('return_type', 'void')
        body = procedure.get('body', '')
        is_function = procedure.get('is_function', False)
        access_level = procedure.get('access_level', 'Public')
        csharp_return_type = self._convert_vb6_type_to_csharp(return_type)
        csharp_params = self._convert_vb6_parameters_to_csharp(parameters)
        csharp_access = 'public' if access_level.lower() == 'public' else 'private'
        method_name = f"{module_name}_{name}" if module_name else name
        method_body = self._generate_method_body(method_name, body, csharp_return_type, is_function, context_map)
        return f"""    {csharp_access} {csharp_return_type} {method_name}({csharp_params})
    {{
        _logger.LogDebug("VB6 procedure '{method_name}' called");
        try
        {{
{method_body}
        }}
        catch (Exception ex)
        {{
            _logger.LogError(ex, "Error in VB6 procedure '{method_name}'");
            {self._generate_error_return(csharp_return_type)}
        }}
    }}"""

    def _generate_method_body(self, name: str, vb6_body: str, return_type: str, is_function: bool, context_map: dict) -> str:
        lines = []
        lines.append("            lock (_lockObject)")
        lines.append("            {")
        if vb6_body and len(vb6_body.strip()) > 0:
            converted_body = self._convert_vb6_body_to_csharp(vb6_body, name, return_type, context_map)
            lines.extend([f"                {line}" for line in converted_body.split('\n') if line.strip()])
        else:
            realistic_impl = self._generate_realistic_implementation(name, return_type, is_function, context_map)
            lines.extend([f"                {line}" for line in realistic_impl.split('\n') if line.strip()])
        lines.append("            }")
        return '\n'.join(lines)

    def _convert_vb6_body_to_csharp(self, vb6_body: str, method_name: str, return_type: str, context_map: dict) -> str:
        csharp_body = vb6_body
        replacements = {
            'Dim ': 'var ',
            ' As Integer': '',
            ' As String': '',
            ' As Boolean': '',
            ' As Long': '',
            ' As Byte': '',
            'Set ': '',
            'Nothing': 'null',
            'True': 'true',
            'False': 'false',
            'And': '&&',
            'Or': '||',
            'Not ': '!',
            '<>': '!=',
            '&': '+',
        }
        for vb6_pattern, csharp_pattern in replacements.items():
            csharp_body = csharp_body.replace(vb6_pattern, csharp_pattern)
        for global_var in context_map.get('state_management', {}).get('global_variables', []):
            var_parts = global_var.split(':')
            var_name = var_parts[0]
            module_name = var_parts[1] if len(var_parts) > 1 else ''
            csharp_var = f"_{self._to_camel_case(f'{module_name}_{var_name}' if module_name else var_name)}"
            csharp_body = csharp_body.replace(var_name, csharp_var)
        for call in context_map.get('module_hierarchy', {}).get('call_graph', []):
            caller = call.get('caller', '')
            callee = call.get('callee', '')
            if callee:
                callee_parts = callee.split('.')
                if len(callee_parts) == 2:
                    callee_module, callee_proc = callee_parts
                    csharp_callee = f"{callee_module}_{callee_proc}"
                    csharp_body = csharp_body.replace(callee_proc, csharp_callee)
        if return_type != 'void' and not 'return' in csharp_body.lower():
            if return_type == 'bool':
                csharp_body += '\nreturn true;'
            elif return_type in ['int', 'long', 'byte']:
                csharp_body += f'\nreturn 0;'
            elif return_type == 'string':
                csharp_body += '\nreturn string.Empty;'
            else:
                csharp_body += f'\nreturn default({return_type});'
        return csharp_body

    def _generate_realistic_implementation(self, method_name: str, return_type: str, is_function: bool, context_map: dict) -> str:
        name_lower = method_name.lower()
        main_workflow = context_map.get('main_workflow', {})
        processing_pattern = main_workflow.get('processing_pattern', 'Sequential')
        if 'initialize' in name_lower or 'init' in name_lower:
            return f"""_logger.LogDebug("Initializing {{method}}...", "{method_name}");
_cmd = 0;
_req = 0;""" + (f'\nreturn {self._get_default_return(return_type)};' if return_type != 'void' else '')
        elif 'process' in name_lower or 'execute' in name_lower:
            impl = f"""_logger.LogDebug("Processing in {{method}}...", "{method_name}");
await Task.Delay(50);
_processedCount++;"""
            if processing_pattern == 'Timer':
                impl += f"\n_logger.LogDebug(\"Timer-based processing for {{method}}\", \"{method_name}\");"
            return impl + (f'\nreturn {self._get_default_return(return_type)};' if return_type != 'void' else '')
        elif 'get' in name_lower or 'retrieve' in name_lower:
            return f"""_logger.LogDebug("Retrieving data in {{method}}...", "{method_name}");
var result = _random.Next(1, 1000);""" + (f'\nreturn {self._get_typed_return(return_type, "result")};' if return_type != 'void' else '')
        elif 'set' in name_lower or 'update' in name_lower:
            return f"""_logger.LogDebug("Setting data in {{method}}...", "{method_name}");
_lastProcessTime = DateTime.Now;""" + (f'\nreturn {self._get_default_return(return_type)};' if return_type != 'void' else '')
        elif 'calculate' in name_lower or 'compute' in name_lower:
            return f"""_logger.LogDebug("Computing in {{method}}...", "{method_name}");
var computation = _bc * 1.5 + _processedCount;""" + (f'\nreturn {self._get_typed_return(return_type, "computation")};' if return_type != 'void' else '')
        elif 'validate' in name_lower or 'check' in name_lower:
            return f"""_logger.LogDebug("Validating in {{method}}...", "{method_name}");
var isValid = _bc > 0 && _tout > 0;""" + (f'\nreturn {self._get_typed_return(return_type, "isValid")};' if return_type != 'void' else '')
        else:
            return f"""_logger.LogDebug("Executing VB6 method {{method}}...", "{method_name}");
var result = _processedCount + _random.Next(1, 100);""" + (f'\nreturn {self._get_typed_return(return_type, "result")};' if return_type != 'void' else '')

    def _generate_execute_async(self, procedures: List, main_logic: dict, context_map: dict) -> str:
        processing_pattern = main_logic.get('processing_pattern', 'Sequential')
        delay_ms = 1000 if processing_pattern == 'Timer' else 500
        entry_point = main_logic.get('entry_point', '')
        entry_call = ""
        if entry_point:
            entry_parts = entry_point.split('.')
            if len(entry_parts) == 2:
                module, proc = entry_parts
                entry_call = f"            {module}_{proc}();\n"
        return f"""    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {{
        _logger.LogInformation("VB6 Converted Worker Service started at: {{time}}", DateTimeOffset.Now);
        try
        {{
            while (!stoppingToken.IsCancellationRequested)
            {{
                await ProcessMainWorkflow(stoppingToken);
                var delay = Math.Max({delay_ms}, (int)(_tout / 30));
                await Task.Delay(delay, stoppingToken);
            }}
        }}
        catch (OperationCanceledException)
        {{
            _logger.LogInformation("Worker service cancellation requested");
        }}
        catch (Exception ex)
        {{
            _logger.LogError(ex, "Fatal error in worker service");
            throw;
        }}
        finally
        {{
            await PerformCleanup();
            _logger.LogInformation("VB6 Converted Worker Service stopped at: {{time}}", DateTimeOffset.Now);
        }}
    }}"""

    def _generate_procedure_calls(self, procedures: List, context_map: dict) -> str:
        calls = []
        module_hierarchy = context_map.get('module_hierarchy', {})
        main_module = module_hierarchy.get('main_module', '')
        call_graph = module_hierarchy.get('call_graph', [])
        module_procs = {}
        for proc in procedures:
            module_name = proc.get('module_name', '')
            if module_name not in module_procs:
                module_procs[module_name] = []
            module_procs[module_name].append(proc)
        ordered_modules = [main_module] + [m for m in module_procs.keys() if m and m != main_module]
        for module_name in ordered_modules:
            if module_name in module_procs:
                for i, procedure in enumerate(module_procs[module_name]):
                    name = procedure.get('name', '')
                    return_type = procedure.get('return_type', 'void')
                    method_name = f"{module_name}_{name}" if module_name else name
                    if name:
                        calls.append(f"            // Call VB6 procedure {i+1} from {module_name or 'unknown module'}")
                        if return_type == 'void':
                            calls.append(f"            {method_name}();")
                        else:
                            calls.append(f"            var result{i+1} = {method_name}();")
                            calls.append(f"            _logger.LogDebug(\"VB6 function {method_name} returned: {{result}}\", result{i+1});")
                        calls.append("")
        if not calls:
            calls.append("            // No VB6 procedures to execute")
            calls.append("            _logger.LogDebug(\"No extracted VB6 procedures found\");")
        return '\n'.join(calls)

    def _convert_vb6_type_to_csharp(self, vb6_type: str) -> str:
        type_map = {
            'Integer': 'int',
            'String': 'string',
            'Boolean': 'bool',
            'Long': 'long',
            'Byte': 'byte',
            'Single': 'float',
            'Double': 'double',
            'Currency': 'decimal',
            'Date': 'DateTime',
            'Object': 'object',
            'Variant': 'object',
            'void': 'void'
        }
        return type_map.get(vb6_type, 'object')

    def _convert_vb6_parameters_to_csharp(self, parameters: List) -> str:
        if not parameters:
            return ""
        csharp_params = []
        for param in parameters:
            if ':' in str(param):
                param_parts = str(param).split(':')
                param_name = param_parts[0].strip()
                param_type = param_parts[1].strip() if len(param_parts) > 1 else 'object'
                csharp_type = self._convert_vb6_type_to_csharp(param_type)
                csharp_params.append(f"{csharp_type} {param_name}")
            else:
                csharp_params.append(f"object {param}")
        return ', '.join(csharp_params)

    def _convert_vb6_default_to_csharp(self, default_value: str, csharp_type: str) -> str:
        if not default_value:
            return ""
        if default_value.lower() in ['nothing', 'null']:
            return " = null"
        elif default_value.lower() == 'true':
            return " = true"
        elif default_value.lower() == 'false':
            return " = false"
        elif default_value.startswith('"') and default_value.endswith('"'):
            return f" = {default_value}"
        elif default_value.isdigit():
            return f" = {default_value}"
        else:
            type_defaults = {
                'int': ' = 0',
                'long': ' = 0L',
                'byte': ' = 0',
                'bool': ' = false',
                'string': ' = string.Empty',
                'object': ' = null'
            }
            return type_defaults.get(csharp_type, "")

    def _to_camel_case(self, name: str) -> str:
        if not name:
            return name
        return name[0].lower() + name[1:] if len(name) > 1 else name.lower()

    def _get_default_return(self, return_type: str) -> str:
        defaults = {
            'int': '0',
            'long': '0L',
            'byte': '0',
            'bool': 'true',
            'string': 'string.Empty',
            'float': '0.0f',
            'double': '0.0',
            'decimal': '0m'
        }
        return defaults.get(return_type, 'null')

    def _get_typed_return(self, return_type: str, variable_name: str) -> str:
        if return_type == 'int':
            return f"(int){variable_name}"
        elif return_type == 'long':
            return f"(long){variable_name}"
        elif return_type == 'byte':
            return f"(byte){variable_name}"
        elif return_type == 'bool':
            return f"({variable_name} != null && {variable_name}.ToString() != \"0\")"
        elif return_type == 'string':
            return f"{variable_name}?.ToString() ?? string.Empty"
        else:
            return f"({return_type}){variable_name}"

    def _generate_error_return(self, return_type: str) -> str:
        if return_type == 'void':
            return ""
        elif return_type == 'bool':
            return "return false;"
        elif return_type in ['int', 'long', 'byte']:
            return "return -1;"
        elif return_type == 'string':
            return "return string.Empty;"
        else:
            return f"return default({return_type});"

    def _get_enhanced_worker_template(self, yaml_summary: str, context_map: dict) -> str:
        main_module = context_map.get('module_hierarchy', {}).get('main_module', 'ConvertedService')
        namespace = f"{self._sanitize_namespace(main_module)}Namespace"
        return f"""using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Logging;
using System;
using System.Threading;
using System.Threading.Tasks;

namespace {namespace};

public class Worker : BackgroundService
{{
    private readonly ILogger<Worker> _logger;
    private int _bc = 30000;
    private long _bcLong = 30000;
    private byte _cmd = 0;
    private byte _req = 0;
    private long _tout = 30000;
    private long _mlngMetaDataTout = 60000;
    private byte _mbytMetaDataReq = 0;
    private int _mintMetaDataBC = 0;
    private readonly object _lockObject = new object();

    public Worker(ILogger<Worker> logger)
    {{
        _logger = logger;
        ClassInitialize();
    }}

    private void ClassInitialize()
    {{
        lock (_lockObject)
        {{
            _cmd = 0;
            _req = 0;
            _tout = 30000;
            _bc = 30000;
            _logger.LogInformation("VB6 Worker Service initialized");
        }}
    }}

    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {{
        _logger.LogInformation("VB6 Converted Worker Service started at: {{time}}", DateTimeOffset.Now);
        while (!stoppingToken.IsCancellationRequested)
        {{
            try
            {{
                await ProcessVB6Logic(stoppingToken);
                await Task.Delay(1000, stoppingToken);
            }}
            catch (OperationCanceledException)
            {{
                _logger.LogInformation("Operation was canceled");
                break;
            }}
            catch (Exception ex)
            {{
                _logger.LogError(ex, "Error in VB6 processing");
                await Task.Delay(5000, stoppingToken);
            }}
        }}
        _logger.LogInformation("VB6 Converted Worker Service stopped at: {{time}}", DateTimeOffset.Now);
    }}

    private async Task ProcessVB6Logic(CancellationToken stoppingToken)
    {{
        _logger.LogInformation("Processing VB6 logic - ByteCount: {{bc}}, Command: {{cmd}}", _bc, _cmd);
        lock (_lockObject)
        {{
            _cmd = (byte)((_cmd + 1) % 256);
            _req = (byte)((_req + 1) % 256);
        }}
        await Task.Delay(100, stoppingToken);
    }}

    public int ByteCount() => _bc;
    public long ByteCountLong() => _bcLong;
    public byte Command() => _cmd;
    public byte Request() => _req;
    public long Timeout() => _tout;
    public long LngMetaDataRequestTimeOut() => _mlngMetaDataTout;
    public byte BytMetaDataRequest() => _mbytMetaDataReq;
    public int IntMetaDataByteCount() => _mintMetaDataBC;

    public void SetServeParameters(object newServeParameters)
    {{
        _logger.LogInformation("VB6 SetServeParameters called");
        lock (_lockObject)
        {{
            if (newServeParameters != null)
            {{
                _cmd = (byte)((_cmd + 1) % 256);
            }}
        }}
    }}

    public void ReinitializeValueCache()
    {{
        _logger.LogInformation("VB6 ReinitializeValueCache called");
        lock (_lockObject)
        {{
            _bc = 30000;
            _bcLong = 30000;
        }}
    }}

    public ReturnCode GetComputedResult(string parameterXYZName, ref ValueResult valResult, 
        int recordNumber = 0, int precision = 0, SeriesDirections seriesDirection = SeriesDirections.Increasing, 
        bool summation = false)
    {{
        _logger.LogInformation("VB6 GetComputedResult called for parameter: {{param}}", parameterXYZName);
        try
        {{
            valResult = new ValueResult 
            {{ 
                Value = new Random().NextDouble() * 100,
                IsValid = true,
                ParameterName = parameterXYZName
            }};
            return ReturnCode.Success;
        }}
        catch (Exception ex)
        {{
            _logger.LogError(ex, "Error in GetComputedResult");
            valResult = new ValueResult {{ IsValid = false }};
            return ReturnCode.Failure;
        }}
    }}
}}

public class ValueResult
{{
    public double Value {{ get; set; }}
    public bool IsValid {{ get; set; }}
    public string ParameterName {{ get; set; }} = string.Empty;
}}

public enum ReturnCode
{{
    Success,
    Failure
}}

public enum SeriesDirections
{{
    Increasing,
    Decreasing
}}
"""

    def _build_complete_project(self, worker_cs: str) -> dict:
        logger.info("Building complete project files", extra={"stage": "generator"})
        safe = {
            "MyWindowsService_csproj": self._get_csproj(),
            "Program_cs": self._get_program_cs(),
            "Worker_cs": worker_cs,
            "appsettings_json": self._get_appsettings(),
            "appsettings_Development_json": self._get_dev_appsettings(),
            "Properties__launchSettings_json": self._get_launch_settings(),
        }
        try:
            validated = CodeFilesModel(**safe)
            return {
                "MyWindowsService.csproj": validated.MyWindowsService_csproj,
                "Program.cs": validated.Program_cs,
                "Worker.cs": validated.Worker_cs,
                "appsettings.json": validated.appsettings_json,
                "appsettings.Development.json": validated.appsettings_Development_json,
                "Properties/launchSettings.json": validated.Properties__launchSettings_json,
            }
        except Exception as e:
            logger.error(f"Project validation error: {e}", extra={"stage": "generator"})
            raise HTTPException(status_code=500, detail="Generated project validation failed")

    def _get_csproj(self) -> str:
        return """<Project Sdk="Microsoft.NET.Sdk.Worker">
  <PropertyGroup>
    <TargetFramework>net9.0</TargetFramework>
    <Nullable>enable</Nullable>
    <ImplicitUsings>enable</ImplicitUsings>
    <UserSecretsId>dotnet-MyWindowsService-$(MSBuildProjectName)</UserSecretsId>
    <UseAppHost>true</UseAppHost>
    <PublishSingleFile>true</PublishSingleFile>
    <SelfContained>true</SelfContained>
  </PropertyGroup>
  <ItemGroup>
    <PackageReference Include="Microsoft.Extensions.Hosting" Version="9.0.0" />
    <PackageReference Include="Microsoft.Extensions.Hosting.WindowsServices" Version="9.0.0" />
    <PackageReference Include="Microsoft.Extensions.Logging.Console" Version="9.0.0" />
    <PackageReference Include="Microsoft.Extensions.Logging.EventLog" Version="9.0.0" />
  </ItemGroup>
</Project>"""

    def _get_program_cs(self) -> str:
        return """using MyWindowsService;
using Microsoft.Extensions.Logging.Configuration;
using Microsoft.Extensions.Logging.EventLog;

var builder = Host.CreateApplicationBuilder(args);
builder.Logging.ClearProviders();
builder.Logging.AddConsole();
if (OperatingSystem.IsWindows())
{
    builder.Logging.AddEventLog();
}
builder.Services.AddHostedService<Worker>();
builder.Services.AddWindowsService(options =>
{
    options.ServiceName = "VB6 Converted Service";
});
var host = builder.Build();
try
{
    await host.RunAsync();
}
catch (Exception ex)
{
    var logger = host.Services.GetRequiredService<ILogger<Program>>();
    logger.LogCritical(ex, "Application terminated unexpectedly");
    throw;
}"""

    def _get_appsettings(self) -> str:
        return """{
  "Logging": {
    "LogLevel": {
      "Default": "Information",
      "Microsoft.Hosting.Lifetime": "Information",
      "MyWindowsService": "Information"
    },
    "Console": {
      "IncludeScopes": true,
      "TimestampFormat": "yyyy-MM-dd HH:mm:ss "
    },
    "EventLog": {
      "LogLevel": {
        "Default": "Warning"
      }
    }
  },
  "WorkerSettings": {
    "ProcessingIntervalMs": 1000,
    "TimeoutMs": 30000,
    "MaxRetries": 50
  }
}"""

    def _get_dev_appsettings(self) -> str:
        return """{
  "logging": {
    "logLevel": {
      "default": "Debug",
      "Microsoft.Hosting.Lifetime": "Information",
      "MyWindowsService": "Debug"
    }
  }
}"""

    def _get_launch_settings(self) -> str:
        return """{
  "profiles": {
    "MyWindowsService": {
      "commandName": "Project",
      "dotnetRunMessages": true,
      "environmentVariables": {
        "DOTNET_ENVIRONMENT": "Development"
      }
    },
    "MyWindowsService (Production)": {
      "commandName": "Project",
      "dotnetRunMessages": false,
      "environmentVariables": {
        "DOTNET_ENVIRONMENT": "Production"
      }
    }
  }
}"""

# Base Agent Class
class BaseAgent:
    def __init__(self, name: str):
        self.name = name
        self.state = AgentState.IDLE

    async def set_state(self, state: AgentState, message: str = ""):
        self.state = state
        logger.info(
            message or f"{self.name} state changed to {state.value}",
            extra={
                "stage": self.name.lower(),
                "agent": self.name,
                "state": state.value,
                "event_type": "state_update"
            }
        )

# Agent classes
class IngestorAgent(BaseAgent):
    def __init__(self):
        super().__init__("IngestorAgent")

    async def run(self, zip_file: Optional[UploadFile], github_link: Optional[str], temp_dir: str) -> List[dict]:
        await self.set_state(AgentState.RUNNING, "Starting ingestion process")
        try:
            if zip_file:
                if zip_file.size and zip_file.size > MAX_FILE_SIZE_MB * 1024 * 1024:
                    await self.set_state(AgentState.FAILED, f"File too large. Maximum size: {MAX_FILE_SIZE_MB}MB")
                    raise HTTPException(status_code=400, detail=f"File too large. Maximum size: {MAX_FILE_SIZE_MB}MB")
                zip_path = os.path.join(temp_dir, "upload.zip")
                await self.set_state(AgentState.RUNNING, "Saving uploaded ZIP file")
                with open(zip_path, "wb") as f:
                    while chunk := await zip_file.read(1024 * 1024):
                        f.write(chunk)
                try:
                    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                        for name in zip_ref.namelist():
                            if not os.path.abspath(os.path.join(temp_dir, name)).startswith(os.path.abspath(temp_dir)):
                                await self.set_state(AgentState.FAILED, "Path traversal detected in ZIP file")
                                raise HTTPException(status_code=400, detail="Path traversal detected in ZIP file")
                        zip_ref.extractall(temp_dir)
                    await self.set_state(AgentState.RUNNING, "Successfully extracted ZIP file")
                except zipfile.BadZipFile:
                    await self.set_state(AgentState.FAILED, "Invalid or corrupted ZIP file")
                    raise HTTPException(status_code=400, detail="Invalid or corrupted ZIP file")
            elif github_link:
                if not any(domain in github_link for domain in ALLOWED_GITHUB_DOMAINS):
                    await self.set_state(AgentState.FAILED, "GitHub domain not allowed")
                    raise HTTPException(status_code=400, detail="GitHub domain not allowed")
                if not re.match(r'^https?://github\.com/[\w-]+/[\w-]+/?$', github_link.strip('/')):
                    await self.set_state(AgentState.FAILED, "Invalid GitHub repository URL")
                    raise HTTPException(status_code=400, detail="Invalid GitHub repository URL")
                github_link = re.sub(r'[^a-zA-Z0-9:/.-]', '', github_link)
                await self.set_state(AgentState.RUNNING, f"Cloning GitHub repository: {github_link}")
                try:
                    Repo.clone_from(github_link, temp_dir, depth=1)
                    await self.set_state(AgentState.RUNNING, f"Successfully cloned repository: {github_link}")
                except Exception as e:
                    await self.set_state(AgentState.FAILED, f"Failed to clone GitHub repo: {str(e)}")
                    raise HTTPException(status_code=400, detail=f"Failed to clone GitHub repo: {str(e)}")
            vb6_files = []
            for root, _, files in os.walk(temp_dir):
                for fname in files:
                    if fname.lower().endswith(('.frm', '.bas', '.cls', '.vbp')):
                        file_path = os.path.join(root, fname)
                        vb6_files.append({"path": file_path, "name": fname})
            if not vb6_files:
                await self.set_state(AgentState.FAILED, "No VB6 files (.frm, .bas, .cls, .vbp) found")
                raise HTTPException(status_code=400, detail="No VB6 files (.frm, .bas, .cls, .vbp) found")
            await self.set_state(AgentState.COMPLETED, f"Found {len(vb6_files)} VB6 files to process")
            return vb6_files
        except Exception as e:
            await self.set_state(AgentState.FAILED, f"IngestorAgent failed: {str(e)}")
            raise

class ParserAgent(BaseAgent):
    def __init__(self):
        super().__init__("ParserAgent")
        self.parser = ParserModule()

    async def run(self, file_info: dict) -> dict:
        file_path = file_info['path']
        file_name = file_info['name']
        await self.set_state(AgentState.RUNNING, f"Parsing file: {file_name}")
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                code = f.read()
            if len(code) > MAX_CODE_LENGTH:
                logger.warning(f"Truncating large file: {file_name} ({len(code)} -> {MAX_CODE_LENGTH} chars)", extra={"stage": "parser"})
                code = code[:MAX_CODE_LENGTH]
            result = await asyncio.to_thread(self.parser.forward, code, file_name)
            result['metadata'] = result.get('metadata', {})
            result['metadata']['file_name'] = file_name
            if file_name.lower().endswith('.frm'):
                result['metadata']['module_type'] = 'Form'
            elif file_name.lower().endswith('.bas'):
                result['metadata']['module_type'] = 'Module'
            elif file_name.lower().endswith('.cls'):
                result['metadata']['module_type'] = 'Class'
            else:
                result['metadata']['module_type'] = 'Unknown'
            await self.set_state(AgentState.COMPLETED, f"Successfully parsed {file_name}: {len(result.get('procedures', []))} procedures, {len(result.get('events', []))} events")
            return result
        except Exception as e:
            await self.set_state(AgentState.FAILED, f"Parser error for {file_name}: {str(e)}")
            return {"procedures": [], "events": [], "globals": [], "dependencies": [], "main_logic": {}, "metadata": {"file_name": file_name, "module_type": "Unknown", "total_lines": 0}}

class ContextAnalyzerAgent(BaseAgent):
    def __init__(self):
        super().__init__("ContextAnalyzerAgent")
        self.analyzer = ContextAnalyzerModule()

    async def run(self, parsed_results: List[dict]) -> dict:
        await self.set_state(AgentState.RUNNING, "Running context analysis")
        try:
            result = await asyncio.to_thread(self.analyzer.forward, parsed_results)
            await self.set_state(AgentState.COMPLETED, "Successfully analyzed application context")
            return result
        except Exception as e:
            await self.set_state(AgentState.FAILED, f"Context analysis error: {str(e)}")
            return {"application_type": "Service", "main_workflow": {}, "data_flow": [], "state_management": {}, "communication": {}, "timing_patterns": {}, "module_hierarchy": {}}

class SummarizerAgent(BaseAgent):
    def __init__(self):
        super().__init__("SummarizerAgent")

    async def run(self, parsed_results: List[dict]) -> str:
        await self.set_state(AgentState.RUNNING, "Starting summarization")
        try:
            valid_results = [r for r in parsed_results if isinstance(r, dict)]
            summary = {
                'procedures': [],
                'events': [],
                'globals': [],
                'dependencies': [],
                'main_logic': {},
                'metadata': {},
                'file_count': len(valid_results)
            }
            for result in valid_results:
                summary['procedures'].extend(result.get('procedures', []))
                summary['events'].extend(result.get('events', []))
                summary['globals'].extend(result.get('globals', []))
                summary['dependencies'].extend(result.get('dependencies', []))
                main_logic = result.get('main_logic', {})
                if main_logic:
                    summary['main_logic'].update(main_logic)
                metadata = result.get('metadata', {})
                if metadata.get('file_name'):
                    summary['metadata'][metadata['file_name']] = metadata
            deps = summary.get('dependencies', [])
            unique_deps = []
            seen = set()
            for dep in deps:
                dep_name = dep.get('name') if isinstance(dep, dict) else str(dep)
                if dep_name and dep_name not in seen:
                    unique_deps.append(dep_name)
                    seen.add(dep_name)
            summary['dependencies'] = unique_deps
            await self.set_state(AgentState.COMPLETED, f"Created summary: {len(summary['procedures'])} procedures, {len(summary['events'])} events, {len(summary['globals'])} globals")
            return yaml.dump(summary, sort_keys=False, default_flow_style=False)
        except Exception as e:
            await self.set_state(AgentState.FAILED, f"Summarizer error: {str(e)}")
            return yaml.dump({'procedures': [], 'events': [], 'globals': [], 'dependencies': [], 'main_logic': {}, 'metadata': {}, 'file_count': 0})

class GeneratorAgent(BaseAgent):
    def __init__(self):
        super().__init__("GeneratorAgent")
        self.generator = GeneratorModule()

    async def run(self, yaml_summary: str, context_map: dict) -> dict:
        await self.set_state(AgentState.RUNNING, "Running code generation")
        try:
            result = await asyncio.to_thread(self.generator.forward, yaml_summary, context_map)
            await self.set_state(AgentState.COMPLETED, "Successfully generated C# project files")
            return result
        except Exception as e:
            await self.set_state(AgentState.FAILED, f"Generation error: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Code generation failed: {str(e)}")

class FileBuilderAgent(BaseAgent):
    def __init__(self):
        super().__init__("FileBuilderAgent")

    async def run(self, code_files: dict) -> tuple[bytes, str]:
        await self.set_state(AgentState.RUNNING, "Starting file building")
        conversion_id = str(uuid.uuid4())
        output_file_path = OUTPUT_DIR / f"{conversion_id}.zip"
        try:
            with tempfile.TemporaryDirectory() as project_dir:
                properties_dir = os.path.join(project_dir, "Properties")
                os.makedirs(properties_dir, exist_ok=True)
                for filename, content in code_files.items():
                    filepath = os.path.join(project_dir, filename.replace("__", "/"))
                    os.makedirs(os.path.dirname(filepath), exist_ok=True)
                    with open(filepath, 'w', encoding='utf-8') as f:
                        f.write(content)
                with zipfile.ZipFile(output_file_path, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                    for root, _, files in os.walk(project_dir):
                        for file in files:
                            file_path = os.path.join(root, file)
                            arc_path = os.path.relpath(file_path, project_dir)
                            zip_file.write(file_path, arc_path)
            if not output_file_path.exists() or output_file_path.stat().st_size == 0:
                await self.set_state(AgentState.FAILED, "Generated ZIP file is empty or missing")
                raise HTTPException(status_code=500, detail="Generated ZIP file is empty or missing")
            await self.set_state(AgentState.COMPLETED, f"Successfully built project ZIP with {len(code_files)} files")
            with open(output_file_path, 'rb') as f:
                result_data = f.read()
            return result_data, conversion_id
        except Exception as e:
            await self.set_state(AgentState.FAILED, f"File builder error: {str(e)}")
            if output_file_path.exists():
                output_file_path.unlink()
            raise HTTPException(status_code=500, detail=f"Project building failed: {str(e)}")

class MCP:
    def __init__(self):
        self.ingestor = IngestorAgent()
        self.parser = ParserAgent()
        self.context_analyzer = ContextAnalyzerAgent()
        self.summarizer = SummarizerAgent()
        self.generator = GeneratorAgent()
        self.filebuilder = FileBuilderAgent()
        self.log_queue = sse_handler.queue
        self.agents = [
            self.ingestor,
            self.parser,
            self.context_analyzer,
            self.summarizer,
            self.generator,
            self.filebuilder
        ]

    async def run(self, zip_file: Optional[UploadFile], github_link: Optional[str]) -> tuple[bytes, str]:
        with tempfile.TemporaryDirectory() as temp_dir:
            await self.set_pipeline_state(AgentState.RUNNING, "Starting VB6 to .NET conversion pipeline")
            try:
                for agent in self.agents:
                    if agent != self.ingestor:
                        await agent.set_state(AgentState.IDLE)
                files = await self.ingestor.run(zip_file, github_link, temp_dir)
                await self.set_pipeline_state(AgentState.RUNNING, f"Processing {len(files)} VB6 files")
                await self.ingestor.set_state(AgentState.COMPLETED)
                await self.parser.set_state(AgentState.RUNNING)
                files_to_process = files[:MAX_FILES]
                if len(files) > MAX_FILES:
                    logger.warning(f"Processing only first {MAX_FILES} files out of {len(files)} total", extra={"stage": "pipeline"})
                parsed_results = await asyncio.gather(*[self.parser.run(f) for f in files_to_process])
                await self.parser.set_state(AgentState.COMPLETED)
                await self.context_analyzer.set_state(AgentState.RUNNING)
                context_map = await self.context_analyzer.run(parsed_results)
                await self.context_analyzer.set_state(AgentState.COMPLETED)
                await self.summarizer.set_state(AgentState.RUNNING)
                yaml_summary = await self.summarizer.run(parsed_results)
                await self.summarizer.set_state(AgentState.COMPLETED)
                await self.generator.set_state(AgentState.RUNNING)
                code_files = await self.generator.run(yaml_summary, context_map)
                await self.generator.set_state(AgentState.COMPLETED)
                await self.filebuilder.set_state(AgentState.RUNNING)
                result, conversion_id = await self.filebuilder.run(code_files)
                await self.filebuilder.set_state(AgentState.COMPLETED)
                await self.set_pipeline_state(AgentState.COMPLETED, "Conversion pipeline completed")
                return result, conversion_id
            except Exception as e:
                await self.set_pipeline_state(AgentState.FAILED, f"Conversion pipeline failed: {str(e)}")
                for agent in self.agents:
                    await agent.set_state(AgentState.FAILED)
                raise

    async def set_pipeline_state(self, state: AgentState, message: str):
        logger.info(
            message,
            extra={
                "stage": "pipeline",
                "agent": "MCP",
                "state": state.value,
                "event_type": "state_update"
            }
        )

mcp = MCP()

@app.get("/")
async def root():
    return {
        "message": "VB6 to .NET Converter API",
        "version": "2.0.6",
        "status": "running",
        "timestamp": time.time()
    }

@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "timestamp": time.time(),
        "azure_openai": "configured" if os.getenv("AZURE_OPENAI_API_KEY") else "not configured"
    }

@app.post("/convert")
async def convert_vb6_to_dotnet(
    zip_file: Optional[UploadFile] = File(None),
    github_link: Optional[str] = Form(None)
):
    if not zip_file and not github_link:
        raise HTTPException(status_code=400, detail="Please provide either a ZIP file or GitHub repository link")
    start_time = time.time()
    try:
        logger.info("Starting VB6 to .NET conversion", extra={"stage": "pipeline", "progress": 0})
        conversion_task = asyncio.create_task(mcp.run(zip_file, github_link))
        result_data, conversion_id = await asyncio.wait_for(conversion_task, timeout=CONVERSION_TIMEOUT_SECONDS)
        duration = time.time() - start_time
        output_file_path = OUTPUT_DIR / f"{conversion_id}.zip"
        with open(output_file_path, 'wb') as f:
            f.write(result_data)
        logger.info(f"Conversion completed successfully in {duration:.2f} seconds", extra={"stage": "pipeline", "progress": 100})
        return {
            "status": "success",
            "conversion_id": conversion_id,
            "duration": duration,
            "message": "Conversion completed. Use the conversion_id to download the file.",
            "download_url": f"/download/{conversion_id}"
        }
    except asyncio.TimeoutError:
        duration = time.time() - start_time
        logger.error(f"Conversion timed out after {duration:.2f} seconds", extra={"stage": "pipeline"})
        raise HTTPException(status_code=504, detail="Conversion process timed out")
    except HTTPException:
        raise
    except Exception as e:
        duration = time.time() - start_time
        logger.error(f"Conversion failed after {duration:.2f} seconds: {str(e)}", extra={"stage": "pipeline"})
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error during conversion: {str(e)}"
        )

@app.get("/download/{conversion_id}")
async def download_converted_file(conversion_id: str):
    file_path = OUTPUT_DIR / f"{conversion_id}.zip"
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found or expired")
    if file_path.stat().st_size == 0:
        file_path.unlink()
        raise HTTPException(status_code=500, detail="File is empty")
    try:
        return FileResponse(
            file_path,
            filename="MyWindowsService.zip",
            headers={"Content-Disposition": "attachment; filename=MyWindowsService.zip"}
        )
    except Exception as e:
        mcp.logger.error(f"Error serving file {conversion_id}: {str(e)}", extra={"stage": "download"})
        raise HTTPException(status_code=500, detail=f"Error serving file: {str(e)}")
    finally:
        try:
            file_path.unlink(missing_ok=True)
            mcp.logger.info(f"Deleted downloaded file: {file_path}", extra={"stage": "download"})
        except Exception as e:
            mcp.logger.error(f"Failed to delete file {file_path}: {str(e)}", extra={"stage": "download"})

@app.get("/stream")
async def stream_conversion_progress():
    async def event_generator():
        while True:
            try:
                event = await asyncio.wait_for(mcp.log_queue.get(), timeout=30.0)
                yield {
                    "event": event.get("event_type", "log"),
                    "data": json.dumps({
                        "message": event.get("message", ""),
                        "level": event.get("level", "INFO"),
                        "timestamp": event.get("timestamp", time.time()),
                        "stage": event.get("stage", "unknown"),
                        "agent": event.get("agent", None),
                        "state": event.get("state", None),
                        "current_agent": event.get("current_agent", None),
                        "progress": event.get("progress", 0),
                        "details": event.get("details", {})
                    })
                }
                if event.get("stage") == "pipeline" and event.get("state") in ["Completed", "Failed"]:
                    break
            except asyncio.TimeoutError:
                yield {
                    "event": "ping",
                    "data": json.dumps({
                        "message": "Keep-alive ping",
                        "timestamp": time.time(),
                        "progress": mcp.sse_handler.progress
                    })
                }
    return EventSourceResponse(event_generator())
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app, 
        host="0.0.0.0", 
        port=8000,
        log_level="info"
    )