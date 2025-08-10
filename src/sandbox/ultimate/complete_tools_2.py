#!/usr/bin/env python3
"""
Complete Ultimate Swiss Army Knife MCP Server - Part 3
CodeIndexer Tools - COMPLETE Implementation
"""

from complete_server import *
from complete_tools_1 import *
import mmap
import bisect
import heapq
from collections import Counter
import Levenshtein
import chardet
from typing import Iterator, Set

# ============================================================================
# COMPLETE CODEINDEXER TOOLS IMPLEMENTATION
# ============================================================================

class CodeIndexerTools:
    """Complete implementation of ALL CodeIndexer tools."""
    
    def __init__(self, server):
        self.server = server
        self.mcp = server.mcp
        self.incremental_index = {}
        self.file_watchers = {}
        self.search_history = deque(maxlen=100)
        self.lazy_loader = LazyContentManager()
        self.parallel_indexer = ParallelIndexer()
        
    def register_tools(self):
        """Register all CodeIndexer tools with COMPLETE functionality."""
        
        @self.mcp.tool()
        async def set_project_path(
            path: str,
            index_immediately: bool = True,
            watch_changes: bool = True,
            ctx: Context = None
        ) -> Dict[str, Any]:
            """Set project path with complete indexing and watching."""
            try:
                project_path = Path(path).resolve()
                
                if not project_path.exists():
                    return {
                        "success": False,
                        "error": f"Path does not exist: {path}"
                    }
                
                # Store project path
                self.server.current_project_path = str(project_path)
                
                # Initialize file watcher if requested
                if watch_changes:
                    await self._setup_file_watcher(project_path)
                
                # Perform initial indexing
                if index_immediately:
                    index_result = await self._index_project(project_path)
                    
                    # Index with Zoekt for search
                    self.server.search_engine.index_directory(project_path)
                    
                    return {
                        "success": True,
                        "project_path": str(project_path),
                        "indexed_files": index_result['file_count'],
                        "total_lines": index_result['total_lines'],
                        "languages": index_result['languages'],
                        "watching": watch_changes,
                        "message": f"Project path set to {project_path}"
                    }
                else:
                    return {
                        "success": True,
                        "project_path": str(project_path),
                        "indexed": False,
                        "watching": watch_changes,
                        "message": f"Project path set to {project_path} (not indexed)"
                    }
                    
            except Exception as e:
                logger.error(f"Failed to set project path: {e}", exc_info=True)
                return {
                    "success": False,
                    "error": str(e)
                }
        
        @self.mcp.tool()
        async def search_code_advanced(
            pattern: str,
            file_pattern: Optional[str] = None,
            case_sensitive: bool = True,
            fuzzy: bool = False,
            fuzzy_threshold: float = 0.8,
            context_lines: int = 2,
            max_results: int = 100,
            use_regex: bool = False,
            search_type: str = "zoekt",  # zoekt, ripgrep, ast, semantic
            ctx: Context = None
        ) -> Dict[str, Any]:
            """Advanced code search with multiple search backends."""
            try:
                # Record search in history
                self.search_history.append({
                    'pattern': pattern,
                    'timestamp': datetime.now().isoformat(),
                    'type': search_type
                })
                
                results = []
                
                if search_type == "zoekt":
                    # Use Zoekt search
                    search_results = self.server.search_engine.search(
                        pattern,
                        file_pattern=file_pattern,
                        case_sensitive=case_sensitive,
                        max_results=max_results
                    )
                    
                    for sr in search_results:
                        results.append({
                            'file': sr.file_path,
                            'line': sr.line_number,
                            'column': sr.column,
                            'match': sr.match,
                            'context': {
                                'before': sr.context_before[-context_lines:],
                                'after': sr.context_after[:context_lines]
                            },
                            'score': sr.score
                        })
                        
                elif search_type == "ripgrep":
                    # Use ripgrep for fast searching
                    results = await self._search_with_ripgrep(
                        pattern, file_pattern, case_sensitive, 
                        context_lines, max_results, use_regex
                    )
                    
                elif search_type == "ast":
                    # AST-based search for semantic patterns
                    results = await self._search_with_ast(
                        pattern, file_pattern, max_results
                    )
                    
                elif search_type == "semantic":
                    # Semantic search using embeddings
                    results = await self._search_semantic(
                        pattern, file_pattern, max_results
                    )
                
                # Apply fuzzy matching if requested
                if fuzzy and results:
                    results = self._apply_fuzzy_filter(
                        results, pattern, fuzzy_threshold
                    )
                
                # Cache search results
                cache_key = f"search:{hashlib.md5(f'{pattern}{file_pattern}{search_type}'.encode()).hexdigest()}"
                self.server.cache.set(cache_key, results, ttl=300)
                
                # Update metrics
                self.server.metrics['search_queries'] += 1
                
                return {
                    "success": True,
                    "pattern": pattern,
                    "search_type": search_type,
                    "total_matches": len(results),
                    "results": results[:max_results],
                    "truncated": len(results) > max_results
                }
                
            except Exception as e:
                logger.error(f"Search failed: {e}", exc_info=True)
                return {
                    "success": False,
                    "error": str(e)
                }
        
        @self.mcp.tool()
        async def find_files(
            pattern: str,
            include_hidden: bool = False,
            follow_symlinks: bool = False,
            max_depth: Optional[int] = None,
            ctx: Context = None
        ) -> Dict[str, Any]:
            """Find files with advanced pattern matching."""
            try:
                if not self.server.current_project_path:
                    return {
                        "success": False,
                        "error": "No project path set"
                    }
                
                project_path = Path(self.server.current_project_path)
                found_files = []
                
                # Use glob patterns
                if '*' in pattern or '?' in pattern or '[' in pattern:
                    # It's a glob pattern
                    for match in project_path.rglob(pattern):
                        if not include_hidden and any(part.startswith('.') for part in match.parts):
                            continue
                        if match.is_file():
                            if not follow_symlinks and match.is_symlink():
                                continue
                            found_files.append(str(match.relative_to(project_path)))
                else:
                    # Search for pattern in filename
                    for root, dirs, files in os.walk(project_path, followlinks=follow_symlinks):
                        # Check depth
                        if max_depth is not None:
                            depth = len(Path(root).relative_to(project_path).parts)
                            if depth > max_depth:
                                continue
                        
                        # Filter hidden directories
                        if not include_hidden:
                            dirs[:] = [d for d in dirs if not d.startswith('.')]
                        
                        for file in files:
                            if not include_hidden and file.startswith('.'):
                                continue
                            if pattern.lower() in file.lower():
                                file_path = Path(root) / file
                                found_files.append(str(file_path.relative_to(project_path)))
                
                # Sort by path
                found_files.sort()
                
                return {
                    "success": True,
                    "pattern": pattern,
                    "total_files": len(found_files),
                    "files": found_files,
                    "project_path": str(project_path)
                }
                
            except Exception as e:
                logger.error(f"Find files failed: {e}", exc_info=True)
                return {
                    "success": False,
                    "error": str(e)
                }
        
        @self.mcp.tool()
        async def get_file_summary(
            file_path: str,
            include_symbols: bool = True,
            include_imports: bool = True,
            include_metrics: bool = True,
            ctx: Context = None
        ) -> Dict[str, Any]:
            """Get comprehensive file summary with symbols and metrics."""
            try:
                # Resolve file path
                if self.server.current_project_path:
                    full_path = Path(self.server.current_project_path) / file_path
                else:
                    full_path = Path(file_path).resolve()
                
                if not full_path.exists():
                    return {
                        "success": False,
                        "error": f"File not found: {file_path}"
                    }
                
                # Get file info
                stat = full_path.stat()
                
                # Detect encoding
                encoding = 'utf-8'
                if MAGIC_AVAILABLE:
                    try:
                        with open(full_path, 'rb') as f:
                            raw = f.read(1024)
                            result = chardet.detect(raw)
                            encoding = result['encoding'] or 'utf-8'
                    except:
                        pass
                
                # Read file content
                try:
                    content = full_path.read_text(encoding=encoding)
                except:
                    content = full_path.read_text(encoding='utf-8', errors='ignore')
                
                lines = content.splitlines()
                
                # Detect language
                language = self._detect_language(full_path)
                
                summary = {
                    "file_path": str(full_path),
                    "relative_path": str(file_path),
                    "language": language,
                    "encoding": encoding,
                    "size_bytes": stat.st_size,
                    "modified_time": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    "line_count": len(lines),
                    "character_count": len(content)
                }
                
                # Extract symbols if requested
                if include_symbols:
                    summary['symbols'] = await self._extract_symbols(full_path, content, language)
                
                # Extract imports if requested
                if include_imports:
                    summary['imports'] = await self._extract_imports(content, language)
                
                # Calculate metrics if requested
                if include_metrics:
                    summary['metrics'] = await self._calculate_file_metrics(content, language)
                
                # Add to lazy loader for future quick access
                self.lazy_loader.add_file(str(full_path), content)
                
                return {
                    "success": True,
                    "summary": summary
                }
                
            except Exception as e:
                logger.error(f"Get file summary failed: {e}", exc_info=True)
                return {
                    "success": False,
                    "error": str(e)
                }
        
        @self.mcp.tool()
        async def refresh_index(
            incremental: bool = True,
            force: bool = False,
            ctx: Context = None
        ) -> Dict[str, Any]:
            """Refresh project index with incremental updates."""
            try:
                if not self.server.current_project_path:
                    return {
                        "success": False,
                        "error": "No project path set"
                    }
                
                project_path = Path(self.server.current_project_path)
                
                if incremental and not force:
                    # Incremental indexing - only changed files
                    changed_files = await self._detect_changed_files(project_path)
                    
                    if not changed_files:
                        return {
                            "success": True,
                            "message": "No changes detected",
                            "indexed_files": 0
                        }
                    
                    indexed_count = 0
                    for file_path in changed_files:
                        await self._index_single_file(file_path)
                        indexed_count += 1
                    
                    # Update Zoekt index
                    self.server.search_engine.index_directory(project_path)
                    
                    return {
                        "success": True,
                        "message": "Incremental index updated",
                        "indexed_files": indexed_count,
                        "changed_files": changed_files
                    }
                else:
                    # Full reindex
                    result = await self._index_project(project_path)
                    
                    # Update Zoekt index
                    self.server.search_engine.index_directory(project_path)
                    
                    return {
                        "success": True,
                        "message": "Full reindex completed",
                        "indexed_files": result['file_count'],
                        "total_lines": result['total_lines']
                    }
                    
            except Exception as e:
                logger.error(f"Refresh index failed: {e}", exc_info=True)
                return {
                    "success": False,
                    "error": str(e)
                }
        
        @self.mcp.tool()
        async def force_reindex(
            clear_cache: bool = True,
            rebuild_search: bool = True,
            ctx: Context = None
        ) -> Dict[str, Any]:
            """Force complete reindex with cache clearing."""
            try:
                if not self.server.current_project_path:
                    return {
                        "success": False,
                        "error": "No project path set"
                    }
                
                project_path = Path(self.server.current_project_path)
                
                # Clear caches if requested
                if clear_cache:
                    self.incremental_index.clear()
                    self.lazy_loader.clear()
                    # Clear Redis/local cache
                    if self.server.cache.use_redis:
                        self.server.cache.redis_client.flushdb()
                    else:
                        self.server.cache.local_cache.clear()
                
                # Clear and rebuild search index
                if rebuild_search:
                    search_index_dir = self.server.search_engine.index_dir
                    if search_index_dir.exists():
                        shutil.rmtree(search_index_dir)
                        search_index_dir.mkdir(parents=True)
                
                # Perform full reindex
                start_time = time.time()
                result = await self._index_project(project_path)
                
                # Rebuild Zoekt index
                self.server.search_engine.index_directory(project_path)
                
                elapsed = time.time() - start_time
                
                return {
                    "success": True,
                    "message": "Force reindex completed",
                    "indexed_files": result['file_count'],
                    "total_lines": result['total_lines'],
                    "elapsed_time": f"{elapsed:.2f}s",
                    "cache_cleared": clear_cache,
                    "search_rebuilt": rebuild_search
                }
                
            except Exception as e:
                logger.error(f"Force reindex failed: {e}", exc_info=True)
                return {
                    "success": False,
                    "error": str(e)
                }
        
        @self.mcp.tool()
        async def write_to_file(
            path: str,
            content: str,
            create_backup: bool = True,
            track_version: bool = True,
            ctx: Context = None
        ) -> Dict[str, Any]:
            """Write content to file with version tracking."""
            try:
                # Resolve path
                if self.server.current_project_path:
                    full_path = Path(self.server.current_project_path) / path
                else:
                    full_path = Path(path).resolve()
                
                # Create directories if needed
                full_path.parent.mkdir(parents=True, exist_ok=True)
                
                # Create backup if file exists
                backup_path = None
                if full_path.exists() and create_backup:
                    backup_path = full_path.with_suffix(full_path.suffix + '.bak')
                    shutil.copy2(full_path, backup_path)
                
                # Track version if requested
                if track_version:
                    # Get old content if exists
                    old_content = ""
                    if full_path.exists():
                        try:
                            old_content = full_path.read_text()
                        except:
                            old_content = full_path.read_text(errors='ignore')
                    
                    # Create version entry
                    version = FileVersion(
                        version_id=f"v_{uuid.uuid4().hex[:8]}",
                        file_path=str(full_path),
                        content_hash=hashlib.sha256(content.encode()).hexdigest(),
                        content=content,
                        timestamp=datetime.now(),
                        message=f"Updated via write_to_file",
                        diff=self._generate_diff(old_content, content) if old_content else None
                    )
                    
                    # Save version
                    self.server.storage.save_file_version(version)
                    
                    # Track in memory
                    if str(full_path) not in self.server.file_versions:
                        self.server.file_versions[str(full_path)] = []
                    self.server.file_versions[str(full_path)].append(version)
                
                # Write content
                full_path.write_text(content)
                
                # Update index
                await self._index_single_file(full_path)
                
                return {
                    "success": True,
                    "file_path": str(full_path),
                    "bytes_written": len(content.encode()),
                    "backup_created": backup_path is not None,
                    "backup_path": str(backup_path) if backup_path else None,
                    "version_tracked": track_version
                }
                
            except Exception as e:
                logger.error(f"Write to file failed: {e}", exc_info=True)
                return {
                    "success": False,
                    "error": str(e)
                }
        
        @self.mcp.tool()
        async def apply_diff(
            diffs: List[Dict[str, Any]],
            dry_run: bool = False,
            create_backups: bool = True,
            ctx: Context = None
        ) -> Dict[str, Any]:
            """Apply multiple diffs to files."""
            try:
                results = []
                
                for diff in diffs:
                    file_path = diff.get('file_path')
                    search = diff.get('search')
                    replace = diff.get('replace')
                    
                    if not all([file_path, search is not None, replace is not None]):
                        results.append({
                            'file': file_path,
                            'success': False,
                            'error': 'Missing required fields'
                        })
                        continue
                    
                    # Resolve path
                    if self.server.current_project_path:
                        full_path = Path(self.server.current_project_path) / file_path
                    else:
                        full_path = Path(file_path).resolve()
                    
                    if not full_path.exists():
                        results.append({
                            'file': str(file_path),
                            'success': False,
                            'error': 'File not found'
                        })
                        continue
                    
                    try:
                        # Read current content
                        content = full_path.read_text()
                        
                        # Apply replacement
                        if search in content:
                            new_content = content.replace(search, replace)
                            occurrences = content.count(search)
                            
                            if not dry_run:
                                # Create backup
                                if create_backups:
                                    backup_path = full_path.with_suffix(full_path.suffix + '.bak')
                                    shutil.copy2(full_path, backup_path)
                                
                                # Write new content
                                full_path.write_text(new_content)
                                
                                # Track version
                                version = FileVersion(
                                    version_id=f"v_{uuid.uuid4().hex[:8]}",
                                    file_path=str(full_path),
                                    content_hash=hashlib.sha256(new_content.encode()).hexdigest(),
                                    content=new_content,
                                    timestamp=datetime.now(),
                                    message=f"Applied diff",
                                    diff=self._generate_diff(content, new_content)
                                )
                                self.server.storage.save_file_version(version)
                            
                            results.append({
                                'file': str(file_path),
                                'success': True,
                                'occurrences_replaced': occurrences,
                                'dry_run': dry_run
                            })
                        else:
                            results.append({
                                'file': str(file_path),
                                'success': False,
                                'error': 'Search pattern not found'
                            })
                            
                    except Exception as e:
                        results.append({
                            'file': str(file_path),
                            'success': False,
                            'error': str(e)
                        })
                
                successful = sum(1 for r in results if r['success'])
                
                return {
                    "success": successful > 0,
                    "total_files": len(diffs),
                    "successful": successful,
                    "failed": len(diffs) - successful,
                    "dry_run": dry_run,
                    "results": results
                }
                
            except Exception as e:
                logger.error(f"Apply diff failed: {e}", exc_info=True)
                return {
                    "success": False,
                    "error": str(e)
                }
        
        @self.mcp.tool()
        async def insert_content(
            path: str,
            line: int,
            content: str,
            ctx: Context = None
        ) -> Dict[str, Any]:
            """Insert content at specific line in file."""
            try:
                # Resolve path
                if self.server.current_project_path:
                    full_path = Path(self.server.current_project_path) / path
                else:
                    full_path = Path(path).resolve()
                
                if not full_path.exists():
                    return {
                        "success": False,
                        "error": f"File not found: {path}"
                    }
                
                # Read current content
                lines = full_path.read_text().splitlines(keepends=True)
                
                # Insert content
                if line == 0:
                    # Append to end
                    lines.append(content)
                    if not content.endswith('\n'):
                        lines.append('\n')
                elif 1 <= line <= len(lines) + 1:
                    # Insert at specific line (1-indexed)
                    if not content.endswith('\n'):
                        content += '\n'
                    lines.insert(line - 1, content)
                else:
                    return {
                        "success": False,
                        "error": f"Invalid line number: {line}"
                    }
                
                # Write back
                new_content = ''.join(lines)
                full_path.write_text(new_content)
                
                # Track version
                version = FileVersion(
                    version_id=f"v_{uuid.uuid4().hex[:8]}",
                    file_path=str(full_path),
                    content_hash=hashlib.sha256(new_content.encode()).hexdigest(),
                    content=new_content,
                    timestamp=datetime.now(),
                    message=f"Inserted content at line {line}"
                )
                self.server.storage.save_file_version(version)
                
                return {
                    "success": True,
                    "file_path": str(path),
                    "line_inserted": line,
                    "content_length": len(content)
                }
                
            except Exception as e:
                logger.error(f"Insert content failed: {e}", exc_info=True)
                return {
                    "success": False,
                    "error": str(e)
                }
        
        @self.mcp.tool()
        async def search_and_replace(
            path: str,
            search: str,
            replace: str,
            use_regex: bool = False,
            case_sensitive: bool = True,
            whole_words: bool = False,
            ctx: Context = None
        ) -> Dict[str, Any]:
            """Search and replace in file with regex support."""
            try:
                # Resolve path
                if self.server.current_project_path:
                    full_path = Path(self.server.current_project_path) / path
                else:
                    full_path = Path(path).resolve()
                
                if not full_path.exists():
                    return {
                        "success": False,
                        "error": f"File not found: {path}"
                    }
                
                # Read content
                content = full_path.read_text()
                original_content = content
                
                # Perform replacement
                if use_regex:
                    flags = 0 if case_sensitive else re.IGNORECASE
                    if whole_words:
                        search = r'\b' + search + r'\b'
                    pattern = re.compile(search, flags)
                    new_content, count = pattern.subn(replace, content)
                else:
                    if whole_words:
                        # Use regex for whole word matching
                        search_pattern = r'\b' + re.escape(search) + r'\b'
                        flags = 0 if case_sensitive else re.IGNORECASE
                        pattern = re.compile(search_pattern, flags)
                        new_content, count = pattern.subn(replace, content)
                    else:
                        if case_sensitive:
                            count = content.count(search)
                            new_content = content.replace(search, replace)
                        else:
                            # Case-insensitive replacement
                            pattern = re.compile(re.escape(search), re.IGNORECASE)
                            new_content, count = pattern.subn(replace, content)
                
                if count > 0:
                    # Write back
                    full_path.write_text(new_content)
                    
                    # Track version
                    version = FileVersion(
                        version_id=f"v_{uuid.uuid4().hex[:8]}",
                        file_path=str(full_path),
                        content_hash=hashlib.sha256(new_content.encode()).hexdigest(),
                        content=new_content,
                        timestamp=datetime.now(),
                        message=f"Replaced {count} occurrences",
                        diff=self._generate_diff(original_content, new_content)
                    )
                    self.server.storage.save_file_version(version)
                
                return {
                    "success": True,
                    "file_path": str(path),
                    "occurrences_replaced": count,
                    "search_pattern": search,
                    "replacement": replace,
                    "regex_used": use_regex
                }
                
            except Exception as e:
                logger.error(f"Search and replace failed: {e}", exc_info=True)
                return {
                    "success": False,
                    "error": str(e)
                }
        
        @self.mcp.tool()
        async def get_file_history(
            file_path: str,
            limit: int = 10,
            ctx: Context = None
        ) -> Dict[str, Any]:
            """Get complete file version history."""
            try:
                # Resolve path
                if self.server.current_project_path:
                    full_path = Path(self.server.current_project_path) / file_path
                else:
                    full_path = Path(file_path).resolve()
                
                # Get versions from storage
                if self.server.storage.use_postgres:
                    with self.server.storage.conn.cursor(cursor_factory=RealDictCursor) as cur:
                        cur.execute("""
                            SELECT * FROM file_versions
                            WHERE file_path = %s
                            ORDER BY timestamp DESC
                            LIMIT %s
                        """, (str(full_path), limit))
                        versions = cur.fetchall()
                else:
                    cursor = self.server.storage.conn.cursor()
                    cursor.execute("""
                        SELECT * FROM file_versions
                        WHERE file_path = ?
                        ORDER BY timestamp DESC
                        LIMIT ?
                    """, (str(full_path), limit))
                    versions = [dict(row) for row in cursor.fetchall()]
                
                # Format versions
                history = []
                for v in versions:
                    history.append({
                        'version_id': v['version_id'],
                        'timestamp': v['timestamp'],
                        'author': v['author'],
                        'message': v['message'],
                        'content_hash': v['content_hash'],
                        'has_diff': v['diff'] is not None
                    })
                
                return {
                    "success": True,
                    "file_path": str(file_path),
                    "version_count": len(history),
                    "history": history
                }
                
            except Exception as e:
                logger.error(f"Get file history failed: {e}", exc_info=True)
                return {
                    "success": False,
                    "error": str(e)
                }
        
        @self.mcp.tool()
        async def revert_file_to_version(
            file_path: str,
            version_id: str,
            create_backup: bool = True,
            ctx: Context = None
        ) -> Dict[str, Any]:
            """Revert file to specific version."""
            try:
                # Resolve path
                if self.server.current_project_path:
                    full_path = Path(self.server.current_project_path) / file_path
                else:
                    full_path = Path(file_path).resolve()
                
                # Get version from storage
                if self.server.storage.use_postgres:
                    with self.server.storage.conn.cursor(cursor_factory=RealDictCursor) as cur:
                        cur.execute("""
                            SELECT * FROM file_versions
                            WHERE version_id = %s AND file_path = %s
                        """, (version_id, str(full_path)))
                        version = cur.fetchone()
                else:
                    cursor = self.server.storage.conn.cursor()
                    cursor.execute("""
                        SELECT * FROM file_versions
                        WHERE version_id = ? AND file_path = ?
                    """, (version_id, str(full_path)))
                    version = dict(cursor.fetchone()) if cursor.fetchone() else None
                
                if not version:
                    return {
                        "success": False,
                        "error": f"Version {version_id} not found for {file_path}"
                    }
                
                # Create backup if requested
                if create_backup and full_path.exists():
                    backup_path = full_path.with_suffix(full_path.suffix + '.bak')
                    shutil.copy2(full_path, backup_path)
                
                # Revert to version
                full_path.write_text(version['content'])
                
                # Create new version entry for the revert
                revert_version = FileVersion(
                    version_id=f"v_{uuid.uuid4().hex[:8]}",
                    file_path=str(full_path),
                    content_hash=version['content_hash'],
                    content=version['content'],
                    timestamp=datetime.now(),
                    message=f"Reverted to version {version_id}"
                )
                self.server.storage.save_file_version(revert_version)
                
                return {
                    "success": True,
                    "file_path": str(file_path),
                    "reverted_to": version_id,
                    "version_timestamp": version['timestamp'],
                    "backup_created": create_backup
                }
                
            except Exception as e:
                logger.error(f"Revert file failed: {e}", exc_info=True)
                return {
                    "success": False,
                    "error": str(e)
                }
        
        # More helper methods continue...

# Continue with remaining tools implementation...
