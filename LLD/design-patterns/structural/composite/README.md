# Composite Design Pattern

## What Is It?

The Composite pattern composes objects into **tree structures** to represent part-whole hierarchies. It lets clients treat individual objects (leaves) and compositions of objects (composites) **uniformly** through a common interface.

## Structure

```
         Component (interface)
         /          \
      Leaf         Composite
                   - children: List<Component>
                   - add(Component)
                   - remove(Component)
```

## ASCII Tree Diagram

```
FileSystemComponent (interface)
├── File (leaf)
│   └── getName(), getSize(), display()
└── Directory (composite)
    ├── children: List<FileSystemComponent>
    ├── add(), remove()
    └── getName(), getSize() [sums children], display() [delegates to children]

Example tree at runtime:
root/
├── src/
│   ├── Main.java (15 KB)
│   ├── Utils.java (8 KB)
│   └── tests/
│       └── MainTest.java (10 KB)
├── docs/
│   ├── README.md (3 KB)
│   └── API.md (5 KB)
└── .gitignore (1 KB)
```

## When to Use

- You need to represent **part-whole hierarchies** (trees)
- You want clients to treat leaves and composites identically
- You want recursive structures where operations propagate down the tree

## When NOT to Use

- The structure is flat (no hierarchy) - adds unnecessary complexity
- Leaf and composite behaviors are fundamentally different and shouldn't share an interface
- You need strict type safety that distinguishes leaves from composites at compile time
- Performance is critical and the overhead of uniform interface + recursion matters

## Real-World Use Cases

| Use Case | Leaf | Composite |
|----------|------|-----------|
| File systems | File | Directory |
| GUI widgets | Button, Label | Panel, Window |
| Organization charts | Employee | Department |
| Menu systems | MenuItem | SubMenu |
| XML/HTML DOM | TextNode | Element |
| Arithmetic expressions | Number | Operation (+, *, etc.) |
| Graphics | Shape | Group of Shapes |

## Pros

- **Open/Closed Principle** - add new component types without changing existing code
- **Uniform treatment** - client code doesn't need if/else for leaf vs composite
- **Simplifies client code** - recursive operations are handled by the structure itself
- **Easy to add new kinds of components**

## Cons

- **Hard to restrict component types** - difficult to allow only certain children in a composite
- **Overly general interface** - leaves may need to implement methods that don't make sense for them (e.g., `add()`)
- **Harder to enforce invariants** across the tree
- **Can make design overly general** when you don't actually need a tree

## Key Design Decisions

1. **Where to declare child management (add/remove)?**
   - In Component interface: more transparent but less safe (leaves get meaningless methods)
   - Only in Composite: safer but client needs to know the type

2. **Should Component store a parent reference?**
   - Useful for traversing up the tree but adds coupling

3. **Caching computed values** (like `getSize()`) can improve performance for large trees
