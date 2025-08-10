"""
Execution history tracking and summary generation with verified outcomes.
"""

import json
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum

from ..types import ActionType, TaskStatus
from .interfaces import ActionLoggerInterface
from .models import Action, LogQuery, LogSummary


class OutcomeStatus(Enum):
    """Status of verified outcomes."""
    SUCCESS = "success"
    FAILURE = "failure"
    PARTIAL = "partial"
    UNKNOWN = "unknown"


@dataclass
class VerifiedOutcome:
    """Represents a verified outcome of an action or task."""
    action_id: str
    outcome_type: str  # file_created, command_executed, error_resolved, etc.
    status: OutcomeStatus
    description: str
    evidence: Dict[str, Any] = field(default_factory=dict)
    verification_timestamp: datetime = field(default_factory=datetime.now)
    verification_method: str = "automatic"  # automatic, manual, external


@dataclass
class TaskExecutionSummary:
    """Summary of task execution with verified outcomes."""
    task_id: str
    task_description: str
    start_time: datetime
    end_time: Optional[datetime]
    duration: Optional[timedelta]
    status: TaskStatus
    actions_count: int
    files_modified: List[str] = field(default_factory=list)
    commands_executed: List[str] = field(default_factory=list)
    errors_encountered: List[str] = field(default_factory=list)
    verified_outcomes: List[VerifiedOutcome] = field(default_factory=list)
    success_rate: float = 0.0


@dataclass
class SessionExecutionHistory:
    """Comprehensive execution history for a session."""
    session_id: str
    start_time: datetime
    end_time: Optional[datetime]
    duration: Optional[timedelta]
    total_actions: int
    task_summaries: List[TaskExecutionSummary] = field(default_factory=list)
    overall_success_rate: float = 0.0
    key_achievements: List[str] = field(default_factory=list)
    remaining_issues: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)


class ExecutionHistoryTracker:
    """
    Tracks execution history and generates comprehensive summaries with verified outcomes.
    """
    
    def __init__(self, logger: ActionLoggerInterface):
        self.logger = logger
        self._verified_outcomes: Dict[str, List[VerifiedOutcome]] = {}
    
    def add_verified_outcome(self, outcome: VerifiedOutcome) -> None:
        """Add a verified outcome for an action."""
        if outcome.action_id not in self._verified_outcomes:
            self._verified_outcomes[outcome.action_id] = []
        self._verified_outcomes[outcome.action_id].append(outcome)
    
    def verify_file_operation_outcome(self, action: Action) -> List[VerifiedOutcome]:
        """
        Verify the outcome of file operations by analyzing the action details.
        """
        outcomes = []
        
        if action.action_type in [ActionType.FILE_CREATE, ActionType.FILE_MODIFY, ActionType.FILE_DELETE]:
            for file_change in action.file_changes:
                # Verify file operation based on change type
                if file_change.change_type == "create":
                    outcome = VerifiedOutcome(
                        action_id=action.id,
                        outcome_type="file_created",
                        status=OutcomeStatus.SUCCESS if file_change.after_content else OutcomeStatus.FAILURE,
                        description=f"File {file_change.file_path} was created",
                        evidence={
                            "file_path": file_change.file_path,
                            "content_length": len(file_change.after_content) if file_change.after_content else 0,
                            "timestamp": file_change.timestamp.isoformat()
                        }
                    )
                elif file_change.change_type == "modify":
                    outcome = VerifiedOutcome(
                        action_id=action.id,
                        outcome_type="file_modified",
                        status=OutcomeStatus.SUCCESS if file_change.after_content != file_change.before_content else OutcomeStatus.FAILURE,
                        description=f"File {file_change.file_path} was modified",
                        evidence={
                            "file_path": file_change.file_path,
                            "before_length": len(file_change.before_content) if file_change.before_content else 0,
                            "after_length": len(file_change.after_content) if file_change.after_content else 0,
                            "content_changed": file_change.after_content != file_change.before_content,
                            "timestamp": file_change.timestamp.isoformat()
                        }
                    )
                elif file_change.change_type == "delete":
                    outcome = VerifiedOutcome(
                        action_id=action.id,
                        outcome_type="file_deleted",
                        status=OutcomeStatus.SUCCESS,  # If logged, deletion was successful
                        description=f"File {file_change.file_path} was deleted",
                        evidence={
                            "file_path": file_change.file_path,
                            "had_content": bool(file_change.before_content),
                            "timestamp": file_change.timestamp.isoformat()
                        }
                    )
                
                outcomes.append(outcome)
        
        return outcomes
    
    def verify_command_execution_outcome(self, action: Action) -> List[VerifiedOutcome]:
        """
        Verify the outcome of command executions by analyzing exit codes and output.
        """
        outcomes = []
        
        if action.action_type == ActionType.COMMAND_EXECUTE and action.command_info:
            cmd_info = action.command_info
            
            # Determine success based on exit code
            if cmd_info.exit_code == 0:
                status = OutcomeStatus.SUCCESS
                description = f"Command '{cmd_info.command}' executed successfully"
            else:
                status = OutcomeStatus.FAILURE
                description = f"Command '{cmd_info.command}' failed with exit code {cmd_info.exit_code}"
            
            outcome = VerifiedOutcome(
                action_id=action.id,
                outcome_type="command_executed",
                status=status,
                description=description,
                evidence={
                    "command": cmd_info.command,
                    "exit_code": cmd_info.exit_code,
                    "duration": cmd_info.duration,
                    "output_length": len(cmd_info.output),
                    "error_output_length": len(cmd_info.error_output),
                    "working_directory": cmd_info.working_directory,
                    "timestamp": cmd_info.timestamp.isoformat()
                }
            )
            
            outcomes.append(outcome)
        
        return outcomes
    
    def verify_error_resolution_outcome(self, action: Action) -> List[VerifiedOutcome]:
        """
        Verify error handling and resolution outcomes.
        """
        outcomes = []
        
        if action.action_type == ActionType.TASK_ERROR and action.error_info:
            error_info = action.error_info
            
            outcome = VerifiedOutcome(
                action_id=action.id,
                outcome_type="error_encountered",
                status=OutcomeStatus.FAILURE,  # Errors are always failures initially
                description=f"Error encountered: {error_info.message}",
                evidence={
                    "error_type": error_info.error_type,
                    "message": error_info.message,
                    "has_stack_trace": bool(error_info.stack_trace),
                    "context_keys": list(error_info.context.keys()) if error_info.context else [],
                    "timestamp": error_info.timestamp.isoformat()
                }
            )
            
            outcomes.append(outcome)
        
        return outcomes
    
    def analyze_task_execution(self, task_id: str, session_id: str = None) -> TaskExecutionSummary:
        """
        Analyze the execution of a specific task and generate a summary with verified outcomes.
        """
        # Get all actions for the task
        query = LogQuery(task_id=task_id, session_id=session_id)
        actions = self.logger.get_actions(query)
        
        if not actions:
            raise ValueError(f"No actions found for task {task_id}")
        
        # Determine task timeline
        start_time = min(action.timestamp for action in actions)
        end_time = max(action.timestamp for action in actions)
        duration = end_time - start_time
        
        # Analyze actions and verify outcomes
        files_modified = []
        commands_executed = []
        errors_encountered = []
        all_verified_outcomes = []
        
        for action in actions:
            # Verify outcomes for this action
            file_outcomes = self.verify_file_operation_outcome(action)
            command_outcomes = self.verify_command_execution_outcome(action)
            error_outcomes = self.verify_error_resolution_outcome(action)
            
            all_verified_outcomes.extend(file_outcomes + command_outcomes + error_outcomes)
            
            # Add any custom verified outcomes for this action
            if action.id in self._verified_outcomes:
                all_verified_outcomes.extend(self._verified_outcomes[action.id])
            
            # Collect summary information
            if action.file_changes:
                files_modified.extend([fc.file_path for fc in action.file_changes])
            
            if action.command_info:
                commands_executed.append(action.command_info.command)
            
            if action.error_info:
                errors_encountered.append(action.error_info.message)
        
        # Calculate success rate
        successful_outcomes = sum(1 for outcome in all_verified_outcomes if outcome.status == OutcomeStatus.SUCCESS)
        total_outcomes = len(all_verified_outcomes)
        success_rate = successful_outcomes / total_outcomes if total_outcomes > 0 else 0.0
        
        # Determine overall task status
        if not errors_encountered and success_rate > 0.8:
            task_status = TaskStatus.COMPLETED
        elif errors_encountered:
            task_status = TaskStatus.ERROR
        else:
            task_status = TaskStatus.IN_PROGRESS
        
        # Find task description from first action
        task_description = actions[0].description if actions else f"Task {task_id}"
        
        return TaskExecutionSummary(
            task_id=task_id,
            task_description=task_description,
            start_time=start_time,
            end_time=end_time,
            duration=duration,
            status=task_status,
            actions_count=len(actions),
            files_modified=list(set(files_modified)),  # Remove duplicates
            commands_executed=commands_executed,
            errors_encountered=errors_encountered,
            verified_outcomes=all_verified_outcomes,
            success_rate=success_rate
        )
    
    def generate_session_history(self, session_id: str) -> SessionExecutionHistory:
        """
        Generate comprehensive execution history for a session with verified outcomes.
        """
        # Get all actions for the session
        query = LogQuery(session_id=session_id)
        actions = self.logger.get_actions(query)
        
        if not actions:
            raise ValueError(f"No actions found for session {session_id}")
        
        # Determine session timeline
        start_time = min(action.timestamp for action in actions)
        end_time = max(action.timestamp for action in actions)
        duration = end_time - start_time
        
        # Group actions by task
        tasks_actions = {}
        for action in actions:
            task_id = action.task_id or "unknown"
            if task_id not in tasks_actions:
                tasks_actions[task_id] = []
            tasks_actions[task_id].append(action)
        
        # Generate task summaries
        task_summaries = []
        for task_id in tasks_actions:
            try:
                task_summary = self.analyze_task_execution(task_id, session_id)
                task_summaries.append(task_summary)
            except Exception as e:
                # Handle cases where task analysis fails
                print(f"Warning: Could not analyze task {task_id}: {e}")
        
        # Calculate overall success rate
        total_outcomes = sum(len(task.verified_outcomes) for task in task_summaries)
        successful_outcomes = sum(
            len([o for o in task.verified_outcomes if o.status == OutcomeStatus.SUCCESS])
            for task in task_summaries
        )
        overall_success_rate = successful_outcomes / total_outcomes if total_outcomes > 0 else 0.0
        
        # Generate key achievements
        key_achievements = []
        for task in task_summaries:
            if task.status == TaskStatus.COMPLETED:
                key_achievements.append(f"Successfully completed {task.task_description}")
            if task.files_modified:
                key_achievements.append(f"Modified {len(task.files_modified)} files in {task.task_description}")
            if task.commands_executed:
                successful_commands = [
                    o for o in task.verified_outcomes 
                    if o.outcome_type == "command_executed" and o.status == OutcomeStatus.SUCCESS
                ]
                if successful_commands:
                    key_achievements.append(f"Successfully executed {len(successful_commands)} commands")
        
        # Generate remaining issues
        remaining_issues = []
        for task in task_summaries:
            if task.status == TaskStatus.ERROR:
                remaining_issues.extend(task.errors_encountered)
            failed_outcomes = [
                o for o in task.verified_outcomes 
                if o.status == OutcomeStatus.FAILURE
            ]
            for outcome in failed_outcomes:
                remaining_issues.append(f"Failed: {outcome.description}")
        
        # Generate recommendations
        recommendations = []
        if overall_success_rate < 0.7:
            recommendations.append("Consider reviewing error handling and retry mechanisms")
        if any(task.status == TaskStatus.ERROR for task in task_summaries):
            recommendations.append("Address remaining errors before proceeding with new tasks")
        if any(len(task.files_modified) > 10 for task in task_summaries):
            recommendations.append("Consider breaking down large file modification tasks")
        
        return SessionExecutionHistory(
            session_id=session_id,
            start_time=start_time,
            end_time=end_time,
            duration=duration,
            total_actions=len(actions),
            task_summaries=task_summaries,
            overall_success_rate=overall_success_rate,
            key_achievements=key_achievements[:10],  # Limit to top 10
            remaining_issues=list(set(remaining_issues))[:10],  # Limit and deduplicate
            recommendations=recommendations
        )
    
    def generate_detailed_completion_summary(self, session_id: str) -> Dict[str, Any]:
        """
        Generate a detailed completion summary using verified historical data.
        """
        history = self.generate_session_history(session_id)
        
        # Generate comprehensive summary
        summary = {
            "session_id": session_id,
            "execution_period": {
                "start_time": history.start_time.isoformat(),
                "end_time": history.end_time.isoformat() if history.end_time else None,
                "duration_seconds": history.duration.total_seconds() if history.duration else 0,
                "duration_human": str(history.duration) if history.duration else "0:00:00"
            },
            "overall_metrics": {
                "total_actions": history.total_actions,
                "total_tasks": len(history.task_summaries),
                "completed_tasks": len([t for t in history.task_summaries if t.status == TaskStatus.COMPLETED]),
                "failed_tasks": len([t for t in history.task_summaries if t.status == TaskStatus.ERROR]),
                "overall_success_rate": round(history.overall_success_rate * 100, 2),
                "total_files_modified": len(set(
                    file_path 
                    for task in history.task_summaries 
                    for file_path in task.files_modified
                )),
                "total_commands_executed": sum(len(task.commands_executed) for task in history.task_summaries),
                "total_errors_encountered": sum(len(task.errors_encountered) for task in history.task_summaries)
            },
            "task_details": [
                {
                    "task_id": task.task_id,
                    "description": task.task_description,
                    "status": task.status.value,
                    "duration_seconds": task.duration.total_seconds() if task.duration else 0,
                    "actions_count": task.actions_count,
                    "files_modified": task.files_modified,
                    "commands_executed": task.commands_executed,
                    "errors_encountered": task.errors_encountered,
                    "success_rate": round(task.success_rate * 100, 2),
                    "verified_outcomes": [
                        {
                            "outcome_type": outcome.outcome_type,
                            "status": outcome.status.value,
                            "description": outcome.description,
                            "evidence": outcome.evidence,
                            "verification_timestamp": outcome.verification_timestamp.isoformat()
                        }
                        for outcome in task.verified_outcomes
                    ]
                }
                for task in history.task_summaries
            ],
            "achievements": history.key_achievements,
            "remaining_issues": history.remaining_issues,
            "recommendations": history.recommendations,
            "verification_summary": {
                "total_outcomes_verified": sum(len(task.verified_outcomes) for task in history.task_summaries),
                "successful_outcomes": sum(
                    len([o for o in task.verified_outcomes if o.status == OutcomeStatus.SUCCESS])
                    for task in history.task_summaries
                ),
                "failed_outcomes": sum(
                    len([o for o in task.verified_outcomes if o.status == OutcomeStatus.FAILURE])
                    for task in history.task_summaries
                ),
                "verification_methods": list(set(
                    outcome.verification_method
                    for task in history.task_summaries
                    for outcome in task.verified_outcomes
                ))
            }
        }
        
        return summary
    
    def export_execution_history(self, session_id: str, format: str = "json") -> str:
        """
        Export execution history in the specified format.
        """
        summary = self.generate_detailed_completion_summary(session_id)
        
        if format.lower() == "json":
            return json.dumps(summary, indent=2)
        elif format.lower() == "markdown":
            return self._generate_markdown_summary(summary)
        else:
            raise ValueError(f"Unsupported export format: {format}")
    
    def _generate_markdown_summary(self, summary: Dict[str, Any]) -> str:
        """Generate a markdown-formatted execution summary."""
        md_lines = [
            f"# Execution Summary for Session {summary['session_id']}",
            "",
            "## Overview",
            f"- **Duration**: {summary['execution_period']['duration_human']}",
            f"- **Total Actions**: {summary['overall_metrics']['total_actions']}",
            f"- **Total Tasks**: {summary['overall_metrics']['total_tasks']}",
            f"- **Success Rate**: {summary['overall_metrics']['overall_success_rate']}%",
            "",
            "## Task Results",
            ""
        ]
        
        for task in summary['task_details']:
            md_lines.extend([
                f"### {task['description']}",
                f"- **Status**: {task['status']}",
                f"- **Success Rate**: {task['success_rate']}%",
                f"- **Files Modified**: {len(task['files_modified'])}",
                f"- **Commands Executed**: {len(task['commands_executed'])}",
                ""
            ])
        
        if summary['achievements']:
            md_lines.extend([
                "## Key Achievements",
                ""
            ])
            for achievement in summary['achievements']:
                md_lines.append(f"- {achievement}")
            md_lines.append("")
        
        if summary['remaining_issues']:
            md_lines.extend([
                "## Remaining Issues",
                ""
            ])
            for issue in summary['remaining_issues']:
                md_lines.append(f"- {issue}")
            md_lines.append("")
        
        if summary['recommendations']:
            md_lines.extend([
                "## Recommendations",
                ""
            ])
            for recommendation in summary['recommendations']:
                md_lines.append(f"- {recommendation}")
        
        return "\n".join(md_lines)