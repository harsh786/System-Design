# Generics, Functional Interfaces, Lambdas, Streams, Optional

These features help you write type-safe and expressive code. In LLD, they appear in repositories, services, strategies, events, validators, and transformation pipelines.

## Generics

Generics let classes and methods work with types while preserving compile-time type safety.

```java
List<String> names = new ArrayList<>();
names.add("Asha");
// names.add(10); // compile-time error
```

Without generics, you would cast manually and risk runtime `ClassCastException`.

## Generic Class

```java
class Box<T> {
    private T value;

    void put(T value) {
        this.value = value;
    }

    T get() {
        return value;
    }
}
```

`T` is a type parameter. Common names:

- `T`: type
- `E`: element
- `K`: key
- `V`: value
- `R`: result

## Generic Method

```java
static <T> T first(List<T> values) {
    if (values.isEmpty()) {
        throw new IllegalArgumentException("empty list");
    }
    return values.get(0);
}
```

The type parameter belongs to the method, not the class.

## Bounded Type Parameter

```java
static <T extends Comparable<T>> T max(List<T> values) {
    T best = values.get(0);
    for (T value : values) {
        if (value.compareTo(best) > 0) {
            best = value;
        }
    }
    return best;
}
```

`T extends Comparable<T>` means T must support comparison.

## Wildcards

Wildcard means "some unknown type".

```java
List<?> values = List.of("A", "B");
Object first = values.get(0);
```

You can read as `Object`, but you cannot safely add arbitrary values except `null`.

## PECS Rule

PECS: Producer Extends, Consumer Super.

Producer example:

```java
static double total(List<? extends Number> numbers) {
    double sum = 0;
    for (Number number : numbers) {
        sum += number.doubleValue();
    }
    return sum;
}
```

`List<? extends Number>` produces `Number` values.

Consumer example:

```java
static void addIntegers(List<? super Integer> values) {
    values.add(1);
    values.add(2);
}
```

`List<? super Integer>` can consume `Integer` values.

## Type Erasure

Java implements generics using type erasure. Generic type information is mostly removed at runtime.

This is why you cannot do:

```java
// new T();              // not allowed
// new List<String>[10]; // not allowed
// value instanceof T;   // not allowed
```

LLD implication: generics protect compile-time code, but runtime behavior still needs explicit type information if you are doing reflection, serialization, or dependency injection.

## Functional Interfaces

A functional interface has exactly one abstract method.

Common built-ins:

| Interface | Method | Meaning |
|---|---|---|
| `Predicate<T>` | `boolean test(T t)` | Checks condition |
| `Function<T,R>` | `R apply(T t)` | Transforms value |
| `Consumer<T>` | `void accept(T t)` | Performs side effect |
| `Supplier<T>` | `T get()` | Supplies value |
| `UnaryOperator<T>` | `T apply(T t)` | T to T |
| `BinaryOperator<T>` | `T apply(T a, T b)` | Two T values to T |
| `Comparator<T>` | `int compare(T a, T b)` | Ordering |
| `Runnable` | `void run()` | Task with no result |
| `Callable<V>` | `V call()` | Task with result/exception |

## Lambda

Lambda is a compact implementation of a functional interface.

```java
Predicate<String> nonBlank = text -> text != null && !text.isBlank();
Function<String, Integer> length = text -> text.length();
Consumer<String> printer = text -> System.out.println(text);
```

## Method Reference

Method references are shorthand for lambdas.

```java
names.forEach(System.out::println);
names.sort(String::compareToIgnoreCase);
```

## Stream

Streams process data declaratively.

```java
List<String> result = names.stream()
    .filter(name -> name.startsWith("A"))
    .map(String::toUpperCase)
    .sorted()
    .toList();
```

Stream stages:

- source: `names.stream()`
- intermediate operations: `filter`, `map`, `sorted`
- terminal operation: `toList`

Streams are lazy. Intermediate operations run only when a terminal operation is called.

## Important Stream Methods

| Method | Type | Meaning |
|---|---|---|
| `filter(Predicate)` | Intermediate | Keep matching values |
| `map(Function)` | Intermediate | Transform each value |
| `flatMap(Function)` | Intermediate | Flatten nested streams |
| `distinct()` | Intermediate | Remove duplicates |
| `sorted()` | Intermediate | Sort natural order |
| `sorted(Comparator)` | Intermediate | Sort custom order |
| `limit(n)` | Intermediate | Take first n |
| `skip(n)` | Intermediate | Skip first n |
| `peek(Consumer)` | Intermediate | Debug/side-effect, use carefully |
| `forEach(Consumer)` | Terminal | Run side effect |
| `toList()` | Terminal | Collect to unmodifiable list-like result |
| `collect(...)` | Terminal | Custom collection/grouping |
| `reduce(...)` | Terminal | Combine into one value |
| `count()` | Terminal | Count elements |
| `anyMatch(Predicate)` | Terminal | Any value matches |
| `allMatch(Predicate)` | Terminal | All values match |
| `noneMatch(Predicate)` | Terminal | No values match |
| `findFirst()` | Terminal | First value as Optional |
| `findAny()` | Terminal | Any value, useful in parallel |
| `min(Comparator)` | Terminal | Minimum |
| `max(Comparator)` | Terminal | Maximum |

## Collectors

```java
Map<String, List<User>> byCity = users.stream()
    .collect(Collectors.groupingBy(User::city));

Map<String, Long> countByCity = users.stream()
    .collect(Collectors.groupingBy(User::city, Collectors.counting()));

String csv = users.stream()
    .map(User::name)
    .collect(Collectors.joining(", "));
```

## Optional

`Optional<T>` represents a value that may be absent.

```java
Optional<User> user = repository.findById("u1");
String name = user.map(User::name).orElse("Guest");
```

Important methods:

| Method | Meaning |
|---|---|
| `of(value)` | Present value, rejects null |
| `ofNullable(value)` | Present if non-null |
| `empty()` | No value |
| `isPresent()` | Has value |
| `isEmpty()` | No value |
| `ifPresent(Consumer)` | Run if present |
| `map(Function)` | Transform present value |
| `flatMap(Function)` | Transform to another Optional |
| `filter(Predicate)` | Keep only if condition passes |
| `orElse(default)` | Return value or eager default |
| `orElseGet(Supplier)` | Return value or lazy default |
| `orElseThrow()` | Return or throw |

LLD rule: `Optional` is good as a return type for "not found". Avoid using it as a field in normal domain objects.

Runnable examples:

- `src/main/java/com/codex/javaconcepts/generics/GenericsExamples.java`
- `src/main/java/com/codex/javaconcepts/streams/StreamsExamples.java`

