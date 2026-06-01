# Interpreter Design Pattern

## What is it?

The Interpreter pattern defines a grammatical representation for a language and provides an interpreter to evaluate sentences in that language. Each rule in the grammar becomes a class, and the language is interpreted by composing these classes into a tree structure (Abstract Syntax Tree).

## When to Use

- You have a simple grammar that can be represented as a class hierarchy
- Efficiency is not a critical concern (small expressions, infrequent evaluation)
- You want to add new expressions easily without modifying existing code
- The grammar doesn't change frequently

## Why Use It

- Cleanly separates grammar rules into individual classes (SRP)
- Easy to extend with new expression types (OCP)
- Expressions are composable - build complex from simple
- Natural fit for DSLs, rules, and query languages

## Class Diagram (ASCII)

```
                    +-------------------+
                    |   <<interface>>   |
                    |    Expression     |
                    +-------------------+
                    | + interpret(ctx)  |
                    +--------+----------+
                             |
            +----------------+----------------+
            |                                 |
   +--------+--------+             +----------+---------+
   | TerminalExpr    |             | NonTerminalExpr    |
   +-----------------+             +--------------------+
   | NumberExpr      |             | AddExpression      |
   | VariableExpr    |             | SubtractExpression |
   | BooleanExpr     |             | MultiplyExpression |
   +-----------------+             | AndExpression      |
                                   | OrExpression       |
                                   | GreaterThanExpr    |
                                   +--------------------+

   +-------------------+
   |     Context       |
   +-------------------+
   | - variables: Map  |
   +-------------------+
   | + setVariable()   |
   | + getVariable()   |
   +-------------------+
```

## Expression Tree Example

```
Expression: (x + y) * z

        [Multiply]
        /        \
    [Add]        [Var:z]
    /    \
[Var:x] [Var:y]
```

## Real-World Use Cases

| Use Case | Example |
|----------|---------|
| Regular Expressions | `java.util.regex.Pattern` |
| SQL Parsers | WHERE clause evaluation |
| Math Evaluators | Calculator apps, spreadsheets |
| Rule Engines | Business rule evaluation (Drools) |
| DSLs | Configuration languages, query builders |
| Compilers | Lexing + parsing phase |
| Template Engines | Thymeleaf, Freemarker expressions |

## Pros and Cons

### Pros
- Easy to change and extend the grammar (add new expression classes)
- Each grammar rule is its own class - simple to understand
- Composable: complex expressions built from simpler ones
- Follows Open/Closed Principle

### Cons
- Complex grammars lead to many classes (class explosion)
- Hard to maintain for large grammars (use parser generators instead)
- Can be slow for complex expressions (no optimization)
- Parsing the input into the tree is often the hardest part

## When NOT to Use

- Grammar is complex (>10-15 rules) - use ANTLR/JavaCC instead
- Performance is critical (tight loops, real-time systems)
- Grammar changes frequently (maintenance burden)
- A simpler approach works (regex, string splitting)

## Running the Example

```bash
javac InterpreterPattern.java && java InterpreterPattern
```
