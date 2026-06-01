# Visitor Design Pattern

## What is the Visitor Pattern?

The Visitor pattern lets you **add new operations to existing object structures without modifying the classes** of the elements on which it operates. It achieves this through **double dispatch** -- selecting a method based on both the runtime type of the element AND the runtime type of the visitor.

## Double Dispatch Explained

Java (and most OOP languages) only supports **single dispatch** -- method resolution is based on the runtime type of the receiver object only. The Visitor pattern simulates double dispatch:

```
1. client calls: shape.accept(visitor)    --> resolved by Shape's runtime type (1st dispatch)
2. shape calls:  visitor.visitCircle(this) --> resolved by Visitor's runtime type (2nd dispatch)
```

The combination of these two polymorphic calls selects the correct behavior based on **both** types.

## When to Use

- Element hierarchy is **stable** (shapes rarely change), but you need to add **new operations frequently**
- You want to keep related behavior together in one class (Single Responsibility)
- Operations need data from unrelated element classes and you don't want to pollute those classes

## When NOT to Use

- Element hierarchy changes frequently (adding a new element forces updating ALL visitors)
- Elements have few operations that rarely change
- Element internals should stay encapsulated (visitor needs access to element state)

## Class Diagram (ASCII)

```
    +------------------+         +--------------------+
    |   <<interface>>  |         |   <<interface>>    |
    |      Shape       |         |   ShapeVisitor     |
    +------------------+         +--------------------+
    | +accept(visitor) |         | +visitCircle()     |
    +--------+---------+         | +visitRectangle()  |
             |                   | +visitTriangle()   |
    +--------+--------+          +--------+-----------+
    |        |        |                   |
+---+--+ +---+----+ +-+------+   +-------+--------+
|Circle| |Rectangle| |Triangle|   |       |        |
+------+ +---------+ +--------+   |       |        |
                              AreaCalc  PerimCalc  XMLExporter
```

**Flow:**
```
Client --> shape.accept(visitor)
              |
              v
        visitor.visitCircle(this)   // element calls back visitor
              |
              v
        [correct method executes based on BOTH types]
```

## Real-World Use Cases

| Use Case | Elements | Visitors |
|----------|----------|----------|
| **Compiler/AST** | Nodes (BinaryExpr, Literal, FuncCall) | TypeChecker, CodeGenerator, Optimizer |
| **Document Export** | Doc parts (Paragraph, Image, Table) | PDFExporter, HTMLExporter, MarkdownExporter |
| **Tax Calculator** | Income types (Salary, Rental, Capital) | FederalTax, StateTax, DeductionCalc |
| **Code Analysis** | AST Nodes | CyclomaticComplexity, DeadCodeDetector, Linter |
| **File Systems** | File types (Text, Image, Video) | SizeCalc, SearchVisitor, AntivirusScanner |
| **Shopping Cart** | Items (Book, Electronics, Food) | TaxVisitor, ShippingVisitor, DiscountVisitor |

## Pros and Cons

### Pros
- **Open/Closed Principle**: Add operations without modifying elements
- **Single Responsibility**: Related behavior grouped in one visitor class
- **Accumulation**: Visitor can accumulate state while traversing structure
- **Double dispatch**: Correct method selection based on two types

### Cons
- **Brittle with new elements**: Adding a new element type requires updating ALL visitor implementations
- **Breaks encapsulation**: Elements must expose enough state for visitors to work
- **Complexity**: Adds indirection that can make code harder to follow
- **Circular dependency**: Elements and visitors know about each other

## Key Insight

> The Visitor pattern trades **ease of adding elements** for **ease of adding operations**. Use it when your type hierarchy is stable but operations evolve frequently.
