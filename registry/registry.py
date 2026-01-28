"""
Block Registry

Central storage for all blocks with discovery, ranking, and wiring validation.
"""

import json
import os
import re
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field
from pathlib import Path


# =============================================================================
# TYPES
# =============================================================================

@dataclass
class TypeSignature:
    """Type signature for a block (input → output)"""
    input_type: str
    output_type: str

    def accepts(self, other_output: str) -> bool:
        """Check if this block can accept output from another block"""
        return types_compatible(other_output, self.input_type)

    def __repr__(self):
        return f"{self.input_type} → {self.output_type}"


@dataclass
class BlockMetrics:
    """Quality and usage metrics"""
    test_count: int = 0
    test_pass_rate: float = 0.0
    usage_count: int = 0
    dependent_count: int = 0

    @property
    def quality_score(self) -> float:
        """Compute overall quality score"""
        return (
            0.4 * self.test_pass_rate +
            0.3 * min(1.0, self.test_count / 20) +
            0.2 * min(1.0, self.usage_count / 1000) +
            0.1 * min(1.0, self.dependent_count / 100)
        )


@dataclass
class Block:
    """A registered block"""
    namespace: str
    name: str
    version: str
    description: str
    signature: TypeSignature
    tags: List[str] = field(default_factory=list)
    category: str = ""
    metrics: BlockMetrics = field(default_factory=BlockMetrics)
    spec: Dict[str, Any] = field(default_factory=dict)
    similar: List[str] = field(default_factory=list)

    @property
    def id(self) -> str:
        return f"{self.namespace}/{self.name}@{self.version}"

    @property
    def full_name(self) -> str:
        return f"{self.namespace}/{self.name}"

    def __repr__(self):
        return f"Block({self.id})"


# =============================================================================
# TYPE COMPATIBILITY
# =============================================================================

def types_compatible(output_type: str, input_type: str) -> bool:
    """Check if output type can wire to input type"""

    # Exact match
    if output_type == input_type:
        return True

    # Any accepts anything
    if input_type == "Any":
        return True

    # Handle generics: List<Text> matches List<Any>
    output_base, output_params = parse_generic(output_type)
    input_base, input_params = parse_generic(input_type)

    if output_base == input_base:
        if not input_params:  # List matches List<X>
            return True
        if input_params == ["Any"]:  # List<Any> matches List<X>
            return True
        # Check params recursively
        if len(output_params) == len(input_params):
            return all(types_compatible(o, i)
                      for o, i in zip(output_params, input_params))

    # Result<T, E> can unwrap to T
    if output_base == "Result" and output_params:
        if types_compatible(output_params[0], input_type):
            return True  # Implicit unwrap (with warning)

    # Option<T> can unwrap to T
    if output_base == "Option" and output_params:
        if types_compatible(output_params[0], input_type):
            return True  # Implicit unwrap (with warning)

    return False


def parse_generic(type_str: str) -> Tuple[str, List[str]]:
    """Parse generic type: 'List<Text>' → ('List', ['Text'])"""
    match = re.match(r'(\w+)<(.+)>$', type_str)
    if match:
        base = match.group(1)
        params_str = match.group(2)
        # Simple split (doesn't handle nested generics perfectly)
        params = [p.strip() for p in params_str.split(',')]
        return base, params
    return type_str, []


# =============================================================================
# REGISTRY
# =============================================================================

class Registry:
    """Central block registry"""

    def __init__(self):
        self.blocks: Dict[str, Block] = {}  # id → Block
        self.by_name: Dict[str, List[str]] = {}  # full_name → [versions]
        self.by_tag: Dict[str, List[str]] = {}  # tag → [block_ids]
        self.by_type: Dict[str, List[str]] = {}  # input_type → [block_ids]

    def register(self, block: Block) -> None:
        """Register a block"""
        # Store by ID
        self.blocks[block.id] = block

        # Index by name
        if block.full_name not in self.by_name:
            self.by_name[block.full_name] = []
        self.by_name[block.full_name].append(block.version)

        # Index by tags
        for tag in block.tags:
            if tag not in self.by_tag:
                self.by_tag[tag] = []
            self.by_tag[tag].append(block.id)

        # Index by input type
        input_type = block.signature.input_type
        if input_type not in self.by_type:
            self.by_type[input_type] = []
        self.by_type[input_type].append(block.id)

    def get(self, block_id: str) -> Optional[Block]:
        """Get block by ID (namespace/name@version)"""
        return self.blocks.get(block_id)

    def get_latest(self, full_name: str) -> Optional[Block]:
        """Get latest version of a block"""
        versions = self.by_name.get(full_name, [])
        if not versions:
            return None
        # Simple version sort (should use semver properly)
        latest = sorted(versions, reverse=True)[0]
        return self.blocks.get(f"{full_name}@{latest}")

    def search(self, query: str, limit: int = 10) -> List[Tuple[Block, float]]:
        """Semantic search for blocks"""
        results = []
        query_lower = query.lower()
        query_words = set(query_lower.split())

        for block in self.blocks.values():
            score = 0.0

            # Name match
            if query_lower in block.name.lower():
                score += 0.4
            if query_lower in block.full_name.lower():
                score += 0.2

            # Tag match
            for tag in block.tags:
                if tag.lower() in query_words or query_lower in tag.lower():
                    score += 0.15

            # Description match
            desc_lower = block.description.lower()
            for word in query_words:
                if word in desc_lower:
                    score += 0.1

            # Quality boost
            score += 0.2 * block.metrics.quality_score

            if score > 0:
                results.append((block, score))

        # Sort by score
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:limit]

    def search_by_type(self, input_type: str = None, output_type: str = None,
                       limit: int = 10) -> List[Block]:
        """Search blocks by type signature"""
        results = []

        for block in self.blocks.values():
            match = True

            if input_type and not types_compatible(input_type, block.signature.input_type):
                # Check if this block can accept the given input type
                if block.signature.input_type != "Any":
                    match = False

            if output_type and not types_compatible(block.signature.output_type, output_type):
                match = False

            if match:
                results.append(block)

        # Sort by quality
        results.sort(key=lambda b: b.metrics.quality_score, reverse=True)
        return results[:limit]

    def find_compatible(self, output_type: str, limit: int = 10) -> List[Block]:
        """Find blocks that can accept the given output type as input"""
        results = []

        for block in self.blocks.values():
            if block.signature.accepts(output_type):
                results.append(block)

        # Sort by quality
        results.sort(key=lambda b: b.metrics.quality_score, reverse=True)
        return results[:limit]

    def find_similar(self, block_id: str) -> List[Block]:
        """Find blocks similar to the given one"""
        block = self.get(block_id)
        if not block:
            return []

        # Search by same tags and type
        candidates = set()
        for tag in block.tags:
            for bid in self.by_tag.get(tag, []):
                if bid != block_id:
                    candidates.add(bid)

        results = []
        for bid in candidates:
            b = self.blocks[bid]
            # Same type signature = very similar
            if (b.signature.input_type == block.signature.input_type and
                b.signature.output_type == block.signature.output_type):
                results.append(b)

        results.sort(key=lambda b: b.metrics.quality_score, reverse=True)
        return results

    def check_duplicate(self, name: str, signature: TypeSignature,
                        tags: List[str]) -> List[Tuple[Block, float]]:
        """Check if similar block already exists (prevent reinvention)"""
        candidates = []

        for block in self.blocks.values():
            score = 0.0

            # Same type signature
            if (block.signature.input_type == signature.input_type and
                block.signature.output_type == signature.output_type):
                score += 0.4

            # Similar name
            if name.lower() in block.name.lower() or block.name.lower() in name.lower():
                score += 0.3

            # Tag overlap
            common_tags = set(tags) & set(block.tags)
            if common_tags:
                score += 0.2 * len(common_tags) / max(len(tags), 1)

            if score >= 0.5:
                candidates.append((block, score))

        candidates.sort(key=lambda x: x[1], reverse=True)
        return candidates

    def stats(self) -> Dict[str, Any]:
        """Registry statistics"""
        return {
            "total_blocks": len(self.blocks),
            "namespaces": len(set(b.namespace for b in self.blocks.values())),
            "tags": len(self.by_tag),
            "avg_quality": sum(b.metrics.quality_score for b in self.blocks.values()) / max(len(self.blocks), 1)
        }


# =============================================================================
# WIRING ENGINE
# =============================================================================

@dataclass
class Wire:
    """A connection between blocks"""
    from_block: str
    from_port: str
    to_block: str
    to_port: str


@dataclass
class FlowStep:
    """A step in a flow"""
    name: str
    block_id: str
    config: Dict[str, Any] = field(default_factory=dict)
    input_from: Optional[str] = None  # "step_name.output"


@dataclass
class ValidationResult:
    """Result of flow validation"""
    valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)


class WiringEngine:
    """Validates and assists with block wiring"""

    def __init__(self, registry: Registry):
        self.registry = registry

    def validate_flow(self, steps: List[FlowStep]) -> ValidationResult:
        """Validate a complete flow"""
        result = ValidationResult(valid=True)

        # Build output type map
        output_types: Dict[str, str] = {}

        for i, step in enumerate(steps):
            block = self.registry.get(step.block_id)
            if not block:
                block = self.registry.get_latest(step.block_id)

            if not block:
                result.valid = False
                result.errors.append(f"Step '{step.name}': Block '{step.block_id}' not found")
                continue

            # Check input wiring
            if step.input_from:
                source_step = step.input_from.split('.')[0]
                if source_step not in output_types:
                    result.valid = False
                    result.errors.append(
                        f"Step '{step.name}': Input source '{source_step}' not found"
                    )
                else:
                    source_type = output_types[source_step]
                    if not block.signature.accepts(source_type):
                        result.valid = False
                        result.errors.append(
                            f"Step '{step.name}': Type mismatch - "
                            f"'{source_step}' outputs {source_type}, "
                            f"but '{block.name}' expects {block.signature.input_type}"
                        )

                    # Warning for implicit unwrap
                    source_base, _ = parse_generic(source_type)
                    if source_base in ("Result", "Option"):
                        if block.signature.input_type not in (source_type, "Any"):
                            result.warnings.append(
                                f"Step '{step.name}': Implicit unwrap of {source_base}. "
                                f"Consider adding explicit error handling."
                            )

            # Record output type
            output_types[step.name] = block.signature.output_type

        # Check for unreachable steps (no input, not first)
        for i, step in enumerate(steps[1:], 1):
            if not step.input_from:
                result.warnings.append(
                    f"Step '{step.name}': No input connection (unreachable?)"
                )

        return result

    def suggest_next(self, current_output_type: str, limit: int = 5) -> List[Block]:
        """Suggest blocks that can follow the current one"""
        return self.registry.find_compatible(current_output_type, limit)

    def auto_wire(self, steps: List[FlowStep]) -> List[FlowStep]:
        """Attempt to auto-wire steps based on types"""
        output_types: Dict[str, str] = {}
        wired_steps = []

        for i, step in enumerate(steps):
            block = self.registry.get(step.block_id)
            if not block:
                block = self.registry.get_latest(step.block_id)

            new_step = FlowStep(
                name=step.name,
                block_id=step.block_id,
                config=step.config,
                input_from=step.input_from
            )

            # Try to auto-wire if no input specified
            if not new_step.input_from and i > 0 and block:
                # Find most recent compatible output
                for prev_name in reversed(list(output_types.keys())):
                    if block.signature.accepts(output_types[prev_name]):
                        new_step.input_from = f"{prev_name}.output"
                        break

            wired_steps.append(new_step)

            if block:
                output_types[step.name] = block.signature.output_type

        return wired_steps


# =============================================================================
# STDLIB - Built-in blocks
# =============================================================================

def create_stdlib() -> Registry:
    """Create registry with standard library blocks"""
    registry = Registry()

    # Core primitives
    stdlib_blocks = [
        Block(
            namespace="core",
            name="transform",
            version="1.0.0",
            description="Apply a pure function to transform data",
            signature=TypeSignature("Any", "Any"),
            tags=["transform", "map", "function", "core"],
            category="core/data",
            metrics=BlockMetrics(test_count=50, test_pass_rate=0.99, usage_count=10000)
        ),
        Block(
            namespace="core",
            name="filter",
            version="1.0.0",
            description="Filter data based on a predicate",
            signature=TypeSignature("Any", "Option<Any>"),
            tags=["filter", "predicate", "conditional", "core"],
            category="core/data",
            metrics=BlockMetrics(test_count=45, test_pass_rate=0.98, usage_count=8000)
        ),
        Block(
            namespace="core",
            name="branch",
            version="1.0.0",
            description="Conditional branching - if/else for data",
            signature=TypeSignature("Any", "Any"),
            tags=["branch", "conditional", "if", "else", "core"],
            category="core/control",
            metrics=BlockMetrics(test_count=40, test_pass_rate=0.99, usage_count=9000)
        ),
        Block(
            namespace="core",
            name="pipe",
            version="1.0.0",
            description="Chain multiple blocks together",
            signature=TypeSignature("Any", "Any"),
            tags=["pipe", "chain", "compose", "core"],
            category="core/composition",
            metrics=BlockMetrics(test_count=30, test_pass_rate=0.99, usage_count=15000)
        ),

        # IO blocks
        Block(
            namespace="io",
            name="file.read",
            version="1.0.0",
            description="Read contents of a file",
            signature=TypeSignature("Text", "Result<Text, IOError>"),
            tags=["file", "read", "io", "filesystem"],
            category="io/file",
            metrics=BlockMetrics(test_count=25, test_pass_rate=0.97, usage_count=5000)
        ),
        Block(
            namespace="io",
            name="file.write",
            version="1.0.0",
            description="Write contents to a file",
            signature=TypeSignature("Text", "Result<None, IOError>"),
            tags=["file", "write", "io", "filesystem"],
            category="io/file",
            metrics=BlockMetrics(test_count=25, test_pass_rate=0.97, usage_count=4500)
        ),
        Block(
            namespace="io",
            name="http.get",
            version="1.0.0",
            description="Make HTTP GET request",
            signature=TypeSignature("Text", "Result<HttpResponse, IOError>"),
            tags=["http", "get", "request", "api", "network"],
            category="io/http",
            metrics=BlockMetrics(test_count=30, test_pass_rate=0.95, usage_count=7000)
        ),
        Block(
            namespace="io",
            name="stdout",
            version="1.0.0",
            description="Write to standard output",
            signature=TypeSignature("Text", "None"),
            tags=["stdout", "print", "console", "output"],
            category="io/console",
            metrics=BlockMetrics(test_count=10, test_pass_rate=0.99, usage_count=12000)
        ),

        # Validation blocks
        Block(
            namespace="stdlib",
            name="email.validate",
            version="1.0.0",
            description="Validate email address format",
            signature=TypeSignature("Text", "Result<Bool, ValidationError>"),
            tags=["email", "validate", "validation", "text"],
            category="validation/text",
            metrics=BlockMetrics(test_count=47, test_pass_rate=0.998, usage_count=52341)
        ),
        Block(
            namespace="stdlib",
            name="url.validate",
            version="1.0.0",
            description="Validate URL format",
            signature=TypeSignature("Text", "Result<Bool, ValidationError>"),
            tags=["url", "validate", "validation", "text"],
            category="validation/text",
            metrics=BlockMetrics(test_count=35, test_pass_rate=0.99, usage_count=23000)
        ),
        Block(
            namespace="stdlib",
            name="phone.validate",
            version="1.0.0",
            description="Validate phone number format (international)",
            signature=TypeSignature("Text", "Result<Bool, ValidationError>"),
            tags=["phone", "validate", "validation", "text"],
            category="validation/text",
            metrics=BlockMetrics(test_count=42, test_pass_rate=0.97, usage_count=12340)
        ),

        # Data processing
        Block(
            namespace="stdlib",
            name="json.parse",
            version="1.0.0",
            description="Parse JSON string to data structure",
            signature=TypeSignature("Text", "Result<Any, ParseError>"),
            tags=["json", "parse", "data", "serialization"],
            category="data/json",
            metrics=BlockMetrics(test_count=50, test_pass_rate=0.99, usage_count=45000)
        ),
        Block(
            namespace="stdlib",
            name="json.stringify",
            version="1.0.0",
            description="Convert data structure to JSON string",
            signature=TypeSignature("Any", "Result<Text, SerializeError>"),
            tags=["json", "stringify", "data", "serialization"],
            category="data/json",
            metrics=BlockMetrics(test_count=45, test_pass_rate=0.99, usage_count=42000)
        ),
        Block(
            namespace="stdlib",
            name="csv.parse",
            version="1.0.0",
            description="Parse CSV string to list of records",
            signature=TypeSignature("Text", "Result<List<Map<Text, Text>>, ParseError>"),
            tags=["csv", "parse", "data", "tabular"],
            category="data/csv",
            metrics=BlockMetrics(test_count=40, test_pass_rate=0.96, usage_count=15000)
        ),

        # Text processing
        Block(
            namespace="stdlib",
            name="text.split",
            version="1.0.0",
            description="Split text by delimiter",
            signature=TypeSignature("Text", "List<Text>"),
            tags=["text", "split", "string", "delimiter"],
            category="text/manipulation",
            metrics=BlockMetrics(test_count=25, test_pass_rate=0.99, usage_count=30000)
        ),
        Block(
            namespace="stdlib",
            name="text.join",
            version="1.0.0",
            description="Join list of text with delimiter",
            signature=TypeSignature("List<Text>", "Text"),
            tags=["text", "join", "string", "delimiter"],
            category="text/manipulation",
            metrics=BlockMetrics(test_count=20, test_pass_rate=0.99, usage_count=28000)
        ),
        Block(
            namespace="stdlib",
            name="text.trim",
            version="1.0.0",
            description="Remove whitespace from start and end",
            signature=TypeSignature("Text", "Text"),
            tags=["text", "trim", "whitespace", "string"],
            category="text/manipulation",
            metrics=BlockMetrics(test_count=15, test_pass_rate=0.99, usage_count=35000)
        ),

        # Error handling
        Block(
            namespace="core",
            name="unwrap",
            version="1.0.0",
            description="Extract value from Result/Option, throw on error",
            signature=TypeSignature("Result<Any, Any>", "Any"),
            tags=["unwrap", "error", "result", "option"],
            category="core/error",
            metrics=BlockMetrics(test_count=20, test_pass_rate=0.99, usage_count=40000)
        ),
        Block(
            namespace="core",
            name="unwrap_or",
            version="1.0.0",
            description="Extract value from Result/Option with fallback",
            signature=TypeSignature("Result<Any, Any>", "Any"),
            tags=["unwrap", "error", "fallback", "default"],
            category="core/error",
            metrics=BlockMetrics(test_count=25, test_pass_rate=0.99, usage_count=35000)
        ),
    ]

    for block in stdlib_blocks:
        registry.register(block)

    return registry


# =============================================================================
# GLOBAL REGISTRY
# =============================================================================

_registry: Optional[Registry] = None


def get_registry() -> Registry:
    """Get global registry instance"""
    global _registry
    if _registry is None:
        _registry = create_stdlib()
    return _registry
