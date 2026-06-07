# Core Language, Strings, Arrays, Comparators, And Time

This section covers Java concepts that are not always shown in OOP/collections diagrams but matter in LLD and interviews.

## Primitive Types

Java has 8 primitive types:

| Type | Meaning | Example |
|---|---|---|
| `byte` | 8-bit integer | raw bytes |
| `short` | 16-bit integer | rarely used |
| `int` | 32-bit integer | counts, indexes |
| `long` | 64-bit integer | IDs, timestamps, money minor units |
| `float` | 32-bit decimal approximation | rarely for business logic |
| `double` | 64-bit decimal approximation | measurements, not money |
| `char` | 16-bit character code unit | individual chars |
| `boolean` | true/false | flags |

LLD rule: do not use `double` for money. Use integer minor units, `BigDecimal`, or a `Money` value object.

## Wrapper Classes

Each primitive has a wrapper:

| Primitive | Wrapper |
|---|---|
| `int` | `Integer` |
| `long` | `Long` |
| `double` | `Double` |
| `boolean` | `Boolean` |
| `char` | `Character` |

Use wrappers when:

- storing in collections, because collections need objects
- representing nullable values
- using generic types

```java
List<Integer> numbers = List.of(1, 2, 3);
```

## Autoboxing And Unboxing

Autoboxing converts primitive to wrapper. Unboxing converts wrapper to primitive.

```java
Integer boxed = 10; // autoboxing
int raw = boxed;    // unboxing
```

Pitfall:

```java
Integer value = null;
// int raw = value; // NullPointerException
```

## Arrays

Arrays are fixed-size indexed containers.

```java
int[] numbers = new int[3];
numbers[0] = 10;

String[] names = {"Asha", "Ravi"};
```

Properties:

- fixed length
- zero-based index
- fast random access
- mutable elements
- covariance can cause runtime errors with object arrays

Arrays are useful for low-level algorithms, fixed-size grids, and performance-sensitive code. For most LLD domain collections, prefer `List`.

## Varargs

Varargs let a method accept zero or more arguments.

```java
static int sum(int... values) {
    int total = 0;
    for (int value : values) {
        total += value;
    }
    return total;
}
```

Inside the method, varargs are an array.

## String

`String` is immutable.

```java
String name = "java";
String upper = name.toUpperCase();
System.out.println(name);  // java
System.out.println(upper); // JAVA
```

Important methods:

| Method | Meaning |
|---|---|
| `length()` | Number of UTF-16 code units |
| `isEmpty()` | Length is zero |
| `isBlank()` | Empty or whitespace only |
| `charAt(i)` | Character at index |
| `substring(a, b)` | Slice |
| `contains(text)` | Contains substring |
| `startsWith(prefix)` | Prefix check |
| `endsWith(suffix)` | Suffix check |
| `indexOf(text)` | First match index |
| `lastIndexOf(text)` | Last match index |
| `replace(a, b)` | Replace text |
| `split(regex)` | Split using regex |
| `trim()` | Remove leading/trailing chars <= space |
| `strip()` | Unicode-aware whitespace strip |
| `toLowerCase()` | Lowercase |
| `toUpperCase()` | Uppercase |
| `equals(other)` | Case-sensitive equality |
| `equalsIgnoreCase(other)` | Case-insensitive equality |

Use `.equals()` for value comparison, not `==`.

## StringBuilder And StringBuffer

`StringBuilder` is mutable and not synchronized. Use it for efficient string construction in one thread.

```java
StringBuilder builder = new StringBuilder();
builder.append("Order ");
builder.append(123);
String result = builder.toString();
```

`StringBuffer` is synchronized and legacy. Most modern code uses `StringBuilder`.

## Comparable

`Comparable<T>` defines natural ordering inside the class.

```java
record Version(int major, int minor) implements Comparable<Version> {
    public int compareTo(Version other) {
        int byMajor = Integer.compare(major, other.major);
        return byMajor != 0 ? byMajor : Integer.compare(minor, other.minor);
    }
}
```

Use when a type has one obvious natural order.

## Comparator

`Comparator<T>` defines external/custom ordering.

```java
users.sort(Comparator.comparing(User::age).thenComparing(User::name));
```

Use when:

- multiple orderings are possible
- you cannot modify the class
- sorting depends on use case

## Packages And Imports

A package groups related classes and prevents name collisions.

```java
package com.example.parking;
```

Imports let you use classes without fully qualified names.

```java
import java.util.List;
import java.util.Map;
```

LLD rule: package by domain/module when possible, not by technical layer only.

Example:

```text
parking/
  ParkingLot.java
  ParkingSpot.java
  Ticket.java
payment/
  PaymentService.java
  PaymentGateway.java
```

## `java.time`

Use `java.time` instead of old `Date` and `Calendar`.

Important types:

| Type | Use |
|---|---|
| `Instant` | Machine timestamp |
| `LocalDate` | Date without time zone |
| `LocalTime` | Time without date/time zone |
| `LocalDateTime` | Date-time without time zone |
| `ZonedDateTime` | Date-time with time zone |
| `Duration` | Time-based amount |
| `Period` | Date-based amount |

LLD examples:

- meeting scheduler: `ZonedDateTime`
- booking date: `LocalDate`
- cache TTL: `Duration`
- event audit time: `Instant`

Runnable example: `src/main/java/com/codex/javaconcepts/core/CoreLanguageExamples.java`

