"""
Multi-file operation coordination and conflict resolution.
"""

import os
import shutil
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional, Set, Tuple
from ..types import FileChange, ErrorInfo


@dataclass
class FileOperation:
    """Represents a single file operation."""
    operation_type: str  # create, modify, delete, move
    file_path: str
    content: Optional[str] = None
    target_path: Optional[str] = None  # For move operations
    dependencies: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class FileConflict:
    """Represents a conflict between file operations."""
    conflict_type: str  # content, dependency, circular, permission
    description: str
    affected_files: List[str] = field(default_factory=list)
    operations: List[FileOperation] = field(default_factory=list)
    severity: str = "medium"  # low, medium, high, critical
    suggested_resolution: Optional[str] = None


@dataclass
class MultiFileTransaction:
    """Represents a transaction of multiple file operations."""
    transaction_id: str
    operations: List[FileOperation] = field(default_factory=list)
    conflicts: List[FileConflict] = field(default_factory=list)
    backup_paths: Dict[str, str] = field(default_factory=dict)
    completed_operations: List[FileOperation] = field(default_factory=list)
    failed_operations: List[FileOperation] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.now)
    
    def add_operation(self, operation: FileOperation) -> None:
        """Add an operation to the transaction."""
        self.operations.append(operation)
    
    def is_completed(self) -> bool:
        """Check if all operations are completed."""
        return len(self.completed_operations) == len(self.operations)
    
    def has_failures(self) -> bool:
        """Check if any operations failed."""
        return len(self.failed_operations) > 0


class MultiFileCoordinator:
    """Coordinates multi-file operations with conflict detection and rollback."""
    
    def __init__(self, workspace_path: str):
        self.workspace_path = Path(workspace_path)
        self.backup_dir = self.workspace_path / ".sandbox_backups"
        self.backup_dir.mkdir(exist_ok=True)
        self.active_transactions: Dict[str, MultiFileTransaction] = {}
    
    def create_transaction(self, transaction_id: str, 
                         operations: List[FileOperation]) -> MultiFileTransaction:
        """Create a new multi-file transaction."""
        transaction = MultiFileTransaction(
            transaction_id=transaction_id,
            operations=operations.copy()
        )
        
        # Detect conflicts before execution
        conflicts = self._detect_conflicts(operations)
        transaction.conflicts = conflicts
        
        self.active_transactions[transaction_id] = transaction
        return transaction
    
    def execute_transaction(self, transaction_id: str) -> bool:
        """Execute a multi-file transaction with rollback on failure."""
        if transaction_id not in self.active_transactions:
            raise ValueError(f"Transaction {transaction_id} not found")
        
        transaction = self.active_transactions[transaction_id]
        
        # Check for critical conflicts
        critical_conflicts = [c for c in transaction.conflicts if c.severity == "critical"]
        if critical_conflicts:
            raise ValueError(f"Cannot execute transaction with critical conflicts: "
                           f"{[c.description for c in critical_conflicts]}")
        
        try:
            # Create backups for existing files
            self._create_backups(transaction)
            
            # Execute operations in dependency order
            ordered_operations = self._order_operations_by_dependencies(transaction.operations)
            
            for operation in ordered_operations:
                try:
                    self._execute_operation(operation, transaction)
                    transaction.completed_operations.append(operation)
                except Exception as e:
                    transaction.failed_operations.append(operation)
                    # Rollback on failure
                    self._rollback_transaction(transaction)
                    raise RuntimeError(f"Operation failed: {operation.file_path} - {str(e)}")
            
            # Clean up backups on success
            self._cleanup_backups(transaction)
            return True
            
        except Exception as e:
            # Ensure rollback is called on any failure
            if not transaction.failed_operations:
                self._rollback_transaction(transaction)
            raise e
        finally:
            # Remove from active transactions
            if transaction_id in self.active_transactions:
                del self.active_transactions[transaction_id]
    
    def _detect_conflicts(self, operations: List[FileOperation]) -> List[FileConflict]:
        """Detect conflicts between file operations."""
        conflicts = []
        
        # Group operations by file path
        file_operations: Dict[str, List[FileOperation]] = {}
        for op in operations:
            if op.file_path not in file_operations:
                file_operations[op.file_path] = []
            file_operations[op.file_path].append(op)
        
        # Check for multiple operations on same file
        for file_path, ops in file_operations.items():
            if len(ops) > 1:
                conflict_types = [op.operation_type for op in ops]
                if "delete" in conflict_types and len(conflict_types) > 1:
                    conflicts.append(FileConflict(
                        conflict_type="content",
                        description=f"Delete operation conflicts with other operations on {file_path}",
                        affected_files=[file_path],
                        operations=ops,
                        severity="critical"
                    ))
                elif conflict_types.count("modify") > 1:
                    conflicts.append(FileConflict(
                        conflict_type="content",
                        description=f"Multiple modify operations on {file_path}",
                        affected_files=[file_path],
                        operations=ops,
                        severity="high",
                        suggested_resolution="Merge modifications or execute sequentially"
                    ))
                elif "create" in conflict_types and ("modify" in conflict_types or "delete" in conflict_types):
                    conflicts.append(FileConflict(
                        conflict_type="content",
                        description=f"Create operation conflicts with other operations on {file_path}",
                        affected_files=[file_path],
                        operations=ops,
                        severity="high",
                        suggested_resolution="Execute operations sequentially"
                    ))
        
        # Check for circular dependencies
        circular_deps = self._detect_circular_dependencies(operations)
        if circular_deps:
            conflicts.append(FileConflict(
                conflict_type="circular",
                description=f"Circular dependencies detected: {' -> '.join(circular_deps)}",
                affected_files=circular_deps,
                severity="critical"
            ))
        
        # Check for missing dependencies
        missing_deps = self._detect_missing_dependencies(operations)
        for missing_dep in missing_deps:
            conflicts.append(FileConflict(
                conflict_type="dependency",
                description=f"Missing dependency: {missing_dep}",
                affected_files=[missing_dep],
                severity="high"
            ))
        
        return conflicts
    
    def _detect_circular_dependencies(self, operations: List[FileOperation]) -> List[str]:
        """Detect circular dependencies in operations."""
        # Build dependency graph
        graph: Dict[str, Set[str]] = {}
        for op in operations:
            graph[op.file_path] = set(op.dependencies)
        
        # Use DFS to detect cycles
        visited = set()
        rec_stack = set()
        
        def has_cycle(node: str, path: List[str]) -> Optional[List[str]]:
            if node in rec_stack:
                # Found cycle, return the cycle path
                cycle_start = path.index(node)
                return path[cycle_start:] + [node]
            
            if node in visited:
                return None
            
            visited.add(node)
            rec_stack.add(node)
            
            for neighbor in graph.get(node, set()):
                cycle = has_cycle(neighbor, path + [node])
                if cycle:
                    return cycle
            
            rec_stack.remove(node)
            return None
        
        for node in graph:
            if node not in visited:
                cycle = has_cycle(node, [])
                if cycle:
                    return cycle
        
        return []
    
    def _detect_missing_dependencies(self, operations: List[FileOperation]) -> List[str]:
        """Detect missing dependencies."""
        operation_files = {op.file_path for op in operations}
        missing_deps = []
        
        for op in operations:
            for dep in op.dependencies:
                if dep not in operation_files:
                    # Check if dependency exists in workspace
                    dep_path = self.workspace_path / dep
                    if not dep_path.exists():
                        missing_deps.append(dep)
        
        return missing_deps
    
    def _order_operations_by_dependencies(self, operations: List[FileOperation]) -> List[FileOperation]:
        """Order operations based on their dependencies using topological sort."""
        # Build adjacency list
        graph: Dict[str, List[str]] = {}
        in_degree: Dict[str, int] = {}
        op_map: Dict[str, FileOperation] = {}
        
        for op in operations:
            op_map[op.file_path] = op
            graph[op.file_path] = op.dependencies.copy()
            in_degree[op.file_path] = 0
        
        # Calculate in-degrees
        for op in operations:
            for dep in op.dependencies:
                if dep in in_degree:
                    in_degree[op.file_path] += 1
        
        # Topological sort using Kahn's algorithm
        queue = [file_path for file_path, degree in in_degree.items() if degree == 0]
        ordered = []
        
        while queue:
            current = queue.pop(0)
            ordered.append(op_map[current])
            
            # Reduce in-degree of neighbors
            for op in operations:
                if current in op.dependencies:
                    in_degree[op.file_path] -= 1
                    if in_degree[op.file_path] == 0:
                        queue.append(op.file_path)
        
        return ordered
    
    def _create_backups(self, transaction: MultiFileTransaction) -> None:
        """Create backups of existing files before modification."""
        backup_timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        transaction_backup_dir = self.backup_dir / f"{transaction.transaction_id}_{backup_timestamp}"
        transaction_backup_dir.mkdir(exist_ok=True)
        
        for operation in transaction.operations:
            if operation.operation_type in ["modify", "delete"]:
                file_path = self.workspace_path / operation.file_path
                if file_path.exists():
                    backup_path = transaction_backup_dir / operation.file_path
                    backup_path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(str(file_path), str(backup_path))
                    transaction.backup_paths[operation.file_path] = str(backup_path)
    
    def _execute_operation(self, operation: FileOperation, 
                         transaction: MultiFileTransaction) -> None:
        """Execute a single file operation."""
        file_path = self.workspace_path / operation.file_path
        
        if operation.operation_type == "create":
            if file_path.exists():
                raise FileExistsError(f"File already exists: {operation.file_path}")
            
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(operation.content or "", encoding='utf-8')
            
        elif operation.operation_type == "modify":
            if not file_path.exists():
                raise FileNotFoundError(f"File not found: {operation.file_path}")
            
            file_path.write_text(operation.content or "", encoding='utf-8')
            
        elif operation.operation_type == "delete":
            if not file_path.exists():
                raise FileNotFoundError(f"File not found: {operation.file_path}")
            
            file_path.unlink()
            
        elif operation.operation_type == "move":
            if not file_path.exists():
                raise FileNotFoundError(f"File not found: {operation.file_path}")
            
            if not operation.target_path:
                raise ValueError("Move operation requires target_path")
            
            target_path = self.workspace_path / operation.target_path
            target_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(file_path), str(target_path))
            
        else:
            raise ValueError(f"Unknown operation type: {operation.operation_type}")
    
    def _rollback_transaction(self, transaction: MultiFileTransaction) -> None:
        """Rollback a failed transaction using backups."""
        try:
            # Restore backed up files
            for file_path, backup_path in transaction.backup_paths.items():
                target_path = self.workspace_path / file_path
                if Path(backup_path).exists():
                    target_path.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(backup_path, str(target_path))
            
            # Remove files created during the transaction
            for operation in transaction.completed_operations:
                if operation.operation_type == "create":
                    file_path = self.workspace_path / operation.file_path
                    if file_path.exists():
                        file_path.unlink()
            
        except Exception as e:
            print(f"Warning: Rollback failed for transaction {transaction.transaction_id}: {e}")
    
    def _cleanup_backups(self, transaction: MultiFileTransaction) -> None:
        """Clean up backup files after successful transaction."""
        for backup_path in transaction.backup_paths.values():
            try:
                Path(backup_path).unlink()
            except Exception:
                pass  # Ignore cleanup errors
        
        # Remove empty backup directories
        try:
            for backup_path in transaction.backup_paths.values():
                backup_dir = Path(backup_path).parent
                if backup_dir.exists() and not any(backup_dir.iterdir()):
                    backup_dir.rmdir()
        except Exception:
            pass  # Ignore cleanup errors
    
    def get_transaction_status(self, transaction_id: str) -> Optional[MultiFileTransaction]:
        """Get the status of a transaction."""
        return self.active_transactions.get(transaction_id)
    
    def list_active_transactions(self) -> List[str]:
        """List all active transaction IDs."""
        return list(self.active_transactions.keys())
    
    def resolve_conflict(self, transaction_id: str, conflict_index: int, 
                        resolution: str) -> bool:
        """Resolve a specific conflict in a transaction."""
        if transaction_id not in self.active_transactions:
            return False
        
        transaction = self.active_transactions[transaction_id]
        if conflict_index >= len(transaction.conflicts):
            return False
        
        conflict = transaction.conflicts[conflict_index]
        
        # Apply resolution based on conflict type and resolution strategy
        if conflict.conflict_type == "content" and resolution == "merge":
            # Implement merge logic for content conflicts
            self._merge_content_operations(conflict.operations)
        elif conflict.conflict_type == "content" and resolution == "sequential":
            # Modify operations to execute sequentially
            self._make_operations_sequential(conflict.operations)
        
        # Remove resolved conflict
        transaction.conflicts.pop(conflict_index)
        return True
    
    def _merge_content_operations(self, operations: List[FileOperation]) -> None:
        """Merge multiple content operations into a single operation."""
        if not operations:
            return
        
        # Simple merge strategy: concatenate all content
        merged_content = ""
        for op in operations:
            if op.content:
                merged_content += op.content + "\n"
        
        # Keep the first operation and update its content
        operations[0].content = merged_content.strip()
        
        # Remove other operations (they will be ignored during execution)
        for i in range(1, len(operations)):
            operations[i].operation_type = "skip"  # Mark as skip
    
    def _make_operations_sequential(self, operations: List[FileOperation]) -> None:
        """Modify operations to execute sequentially by adding dependencies."""
        for i in range(1, len(operations)):
            # Make each operation depend on the previous one
            prev_file = operations[i-1].file_path
            if prev_file not in operations[i].dependencies:
                operations[i].dependencies.append(prev_file)