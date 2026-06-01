# Abstract Factory Design Pattern

## What Is It?

Abstract Factory provides an interface for creating **families of related objects** without specifying their concrete classes. It encapsulates a group of factories that share a common theme.

## When to Use

- System must be independent of how its products are created
- System needs to work with multiple families of products
- Products in a family are designed to work together and you need to enforce this constraint
- You want to provide a library of products revealing only interfaces, not implementations

## Why Use It

- Ensures compatibility between products of the same family
- Isolates client code from concrete implementations
- Makes exchanging product families easy (swap one factory, entire UI changes)
- Promotes consistency among products

## Class Diagram (ASCII)

```
         ┌─────────────────────┐
         │    <<interface>>     │
         │      UIFactory       │
         ├─────────────────────┤
         │ +createButton()     │
         │ +createTextField()  │
         │ +createCheckbox()   │
         └──────────┬──────────┘
                    │
        ┌───────────┴───────────┐
        │                       │
┌───────┴────────┐   ┌─────────┴──────┐
│WindowsUIFactory│   │  MacUIFactory   │
├────────────────┤   ├────────────────-┤
│+createButton() │   │+createButton()  │
│+createTextField│   │+createTextField()│
│+createCheckbox │   │+createCheckbox() │
└───────┬────────┘   └────────┬────────┘
        │                      │
        ▼                      ▼
 WindowsButton            MacButton
 WindowsTextField         MacTextField
 WindowsCheckbox          MacCheckbox

        │                      │
        ▼                      ▼
┌───────────────┐     ┌───────────────┐
│ <<interface>> │     │ <<interface>> │
│    Button     │     │   TextField   │  ... Checkbox
└───────────────┘     └───────────────┘
```

## Real-World Use Cases

| Use Case | Families | Products |
|----------|----------|----------|
| **UI Toolkits** | Windows, Mac, Linux | Button, TextField, Menu |
| **Database Access** | MySQL, PostgreSQL, Oracle | Connection, Command, Reader |
| **Document Generators** | PDF, HTML, Word | Header, Paragraph, Table |
| **Game Assets** | Medieval, Sci-Fi, Modern | Soldier, Weapon, Building |
| **Cloud Providers** | AWS, Azure, GCP | Storage, Compute, Queue |

## Abstract Factory vs Factory Method

| Aspect | Factory Method | Abstract Factory |
|--------|---------------|-----------------|
| **Scope** | Creates ONE product | Creates FAMILY of products |
| **Mechanism** | Inheritance (subclass decides) | Composition (factory object) |
| **Complexity** | Simpler | More complex |
| **Flexibility** | One dimension of variation | Multiple dimensions |
| **Example** | `createButton()` in subclass | Factory object creates Button + TextField + Checkbox |

## Pros and Cons

### Pros
- **Single Responsibility**: Product creation code isolated in one place
- **Open/Closed**: New families added without changing existing code
- **Consistency**: Guarantees products from same family work together
- **Loose Coupling**: Client code decoupled from concrete products

### Cons
- **Complexity**: Many new interfaces and classes introduced
- **Rigidity**: Adding a new product type (e.g., Slider) requires changing ALL factories
- **Overkill**: For simple scenarios with few product types

## When NOT to Use

- Only one product type exists (use Factory Method instead)
- Product families rarely change
- Products from different families can be mixed freely
- Simple applications where direct instantiation suffices
- When adding new product types is more frequent than adding new families

## How to Run

```bash
javac AbstractFactoryPattern.java
java AbstractFactoryPattern
```
