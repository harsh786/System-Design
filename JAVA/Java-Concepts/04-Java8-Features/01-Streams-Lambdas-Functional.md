# Java 8+ Features - Complete LLD Interview Reference

---

## 1. Lambda Expressions

### Syntax

```java
// Expression lambda (single expression, implicit return)
(parameters) -> expression

// Block lambda (multiple statements, explicit return needed)
(parameters) -> { statements; return value; }

// Examples
Runnable r = () -> System.out.println("Hello");
Comparator<String> c = (a, b) -> a.compareTo(b);
Function<Integer, Integer> square = x -> x * x;  // single param: parens optional
BiFunction<Integer, Integer, Integer> add = (a, b) -> a + b;
```

### Type Inference

```java
// Compiler infers parameter types from the target functional interface
// Explicit types
BiFunction<String, String, Integer> f1 = (String a, String b) -> a.length() + b.length();

// Inferred types (preferred)
BiFunction<String, String, Integer> f2 = (a, b) -> a.length() + b.length();

// Cannot mix: (String a, b) -> ... is ILLEGAL

// var in lambda parameters (Java 11+) - useful for annotations
BiFunction<String, String, Integer> f3 = (@NonNull var a, @NonNull var b) -> a.length() + b.length();
```

### Method References

Four kinds of method references:

```java
// 1. Static method reference: ClassName::staticMethod
Function<String, Integer> parseInt = Integer::parseInt;
// Equivalent: s -> Integer.parseInt(s)

List<String> nums = List.of("1", "2", "3");
List<Integer> parsed = nums.stream().map(Integer::parseInt).toList();

// 2. Instance method of a particular object: instance::method
String prefix = "Hello ";
Function<String, String> greeter = prefix::concat;
// Equivalent: s -> prefix.concat(s)

PrintStream out = System.out;
Consumer<String> printer = out::println;

// 3. Instance method of an arbitrary object of a type: ClassName::instanceMethod
Function<String, Integer> length = String::length;
// Equivalent: s -> s.length()

BiPredicate<String, String> startsWith = String::startsWith;
// Equivalent: (s, prefix) -> s.startsWith(prefix)

Comparator<String> comp = String::compareToIgnoreCase;
// Equivalent: (a, b) -> a.compareToIgnoreCase(b)

// 4. Constructor reference: ClassName::new
Supplier<ArrayList<String>> listFactory = ArrayList::new;
Function<Integer, ArrayList<String>> listWithCapacity = ArrayList::new;
// Equivalent: () -> new ArrayList<>() / capacity -> new ArrayList<>(capacity)

Function<String, StringBuilder> sbFactory = StringBuilder::new;

// Array constructor reference
Function<Integer, String[]> arrayFactory = String[]::new;
// Equivalent: size -> new String[size]
// Useful with: stream.toArray(String[]::new)
```

### Effectively Final Variables

```java
// Variables used in lambdas must be effectively final (not reassigned after init)
String name = "World";  // effectively final - never reassigned
Runnable r = () -> System.out.println("Hello " + name);

// ILLEGAL:
String greeting = "Hi";
greeting = "Hello";  // reassignment
Runnable r2 = () -> System.out.println(greeting);  // COMPILE ERROR

// Workarounds for mutable state
// 1. Use AtomicInteger/AtomicReference
AtomicInteger counter = new AtomicInteger(0);
Runnable increment = () -> counter.incrementAndGet();  // OK - reference is final

// 2. Use single-element array
int[] mutable = {0};
Runnable inc = () -> mutable[0]++;  // OK - array reference is final

// 3. Use instance/static fields (no restriction)
class Counter {
    private int count = 0;
    Runnable incrementer = () -> count++;  // OK - captures 'this'
}
```

### Lambda vs Anonymous Class - Key Differences

| Aspect | Lambda | Anonymous Class |
|--------|--------|-----------------|
| Type | Functional interface only (1 abstract method) | Any interface or abstract class |
| `this` reference | Refers to enclosing class | Refers to anonymous class itself |
| Compilation | Invokedynamic (lighter) | Separate .class file |
| State | Cannot have instance fields | Can have fields and state |
| Shadowing | Cannot shadow enclosing variables | Can shadow enclosing variables |
| Verbosity | Concise | Verbose |
| Serialization | Possible but discouraged | Standard serialization |

```java
public class LambdaVsAnonymous {
    private String name = "Outer";

    public void demonstrate() {
        // 'this' in lambda refers to enclosing instance
        Runnable lambda = () -> System.out.println(this.name);  // prints "Outer"

        // 'this' in anonymous class refers to anonymous class instance
        Runnable anon = new Runnable() {
            private String name = "Inner";
            @Override
            public void run() {
                System.out.println(this.name);  // prints "Inner"
            }
        };

        // Lambda cannot implement multiple methods
        // Anonymous class can:
        Iterator<String> iter = new Iterator<String>() {
            int index = 0;  // can have state
            String[] data = {"a", "b", "c"};

            @Override public boolean hasNext() { return index < data.length; }
            @Override public String next() { return data[index++]; }
        };
    }
}
```

---

## 2. Functional Interfaces

### @FunctionalInterface Annotation

```java
@FunctionalInterface  // Optional but recommended - compile error if > 1 abstract method
public interface Transformer<T, R> {
    R transform(T input);

    // Allowed: default methods, static methods, methods from Object
    default Transformer<T, R> logged() {
        return input -> {
            System.out.println("Input: " + input);
            R result = transform(input);
            System.out.println("Output: " + result);
            return result;
        };
    }

    static <T> Transformer<T, T> identity() {
        return t -> t;
    }

    // These don't count as abstract (from Object):
    // boolean equals(Object o);
    // String toString();
    // int hashCode();
}
```

### Built-in Functional Interfaces (java.util.function)

#### Predicate<T> - Takes T, returns boolean

```java
@FunctionalInterface
public interface Predicate<T> {
    boolean test(T t);

    // Default methods
    default Predicate<T> and(Predicate<? super T> other);
    default Predicate<T> or(Predicate<? super T> other);
    default Predicate<T> negate();

    // Static methods
    static <T> Predicate<T> isEqual(Object targetRef);
    static <T> Predicate<T> not(Predicate<? super T> target);  // Java 11
}

// Examples
Predicate<String> isEmpty = String::isEmpty;
Predicate<String> isNotEmpty = Predicate.not(String::isEmpty);  // Java 11
Predicate<String> startsWithA = s -> s.startsWith("A");
Predicate<String> longerThan5 = s -> s.length() > 5;

// Composition
Predicate<String> startsWithAAndLong = startsWithA.and(longerThan5);
Predicate<String> startsWithAOrLong = startsWithA.or(longerThan5);
Predicate<String> doesNotStartWithA = startsWithA.negate();

// isEqual - null-safe equality check
Predicate<String> isHello = Predicate.isEqual("Hello");
isHello.test("Hello");  // true
isHello.test(null);     // false

// Usage with streams
List<String> filtered = names.stream()
    .filter(startsWithA.and(longerThan5))
    .collect(Collectors.toList());
```

#### Function<T, R> - Takes T, returns R

```java
@FunctionalInterface
public interface Function<T, R> {
    R apply(T t);

    // Default methods
    default <V> Function<V, R> compose(Function<? super V, ? extends T> before);
    default <V> Function<T, V> andThen(Function<? super R, ? extends V> after);

    // Static method
    static <T> Function<T, T> identity();
}

// Examples
Function<String, Integer> length = String::length;
Function<Integer, Integer> doubled = x -> x * 2;
Function<String, String> toUpper = String::toUpperCase;

// compose: applies 'before' first, then this
// doubled.compose(length) = first get length, then double it
Function<String, Integer> doubleLengthCompose = doubled.compose(length);
doubleLengthCompose.apply("hello");  // 10

// andThen: applies this first, then 'after'
// length.andThen(doubled) = first get length, then double it
Function<String, Integer> doubleLengthAndThen = length.andThen(doubled);
doubleLengthAndThen.apply("hello");  // 10

// identity
Function<String, String> id = Function.identity();
id.apply("hello");  // "hello"

// Chaining
Function<String, String> pipeline = toUpper
    .andThen(s -> s.trim())
    .andThen(s -> s.replace(" ", "_"));
pipeline.apply("  hello world  ");  // "HELLO_WORLD"
```

#### Consumer<T> - Takes T, returns void

```java
@FunctionalInterface
public interface Consumer<T> {
    void accept(T t);

    default Consumer<T> andThen(Consumer<? super T> after);
}

// Examples
Consumer<String> print = System.out::println;
Consumer<String> log = s -> logger.info("Processing: {}", s);
Consumer<List<String>> clear = List::clear;

// Chaining with andThen
Consumer<String> printAndLog = print.andThen(log);
printAndLog.accept("Hello");  // prints then logs

// Usage
List<String> names = List.of("Alice", "Bob");
names.forEach(print.andThen(s -> System.out.println(s.length())));
```

#### Supplier<T> - Takes nothing, returns T

```java
@FunctionalInterface
public interface Supplier<T> {
    T get();
    // No default or static methods
}

// Examples
Supplier<LocalDateTime> now = LocalDateTime::now;
Supplier<List<String>> listFactory = ArrayList::new;
Supplier<Double> random = Math::random;
Supplier<UUID> uuidGen = UUID::randomUUID;

// Lazy evaluation
public <T> T getOrDefault(T value, Supplier<T> defaultSupplier) {
    return value != null ? value : defaultSupplier.get();  // only computed if needed
}

// Factory pattern
Supplier<Connection> connectionFactory = () -> DriverManager.getConnection(url, user, pass);

// Usage with Optional
Optional<String> opt = Optional.empty();
String result = opt.orElseGet(() -> computeExpensiveDefault());  // lazy
```

#### BiFunction<T, U, R> - Takes T and U, returns R

```java
@FunctionalInterface
public interface BiFunction<T, U, R> {
    R apply(T t, U u);

    default <V> BiFunction<T, U, V> andThen(Function<? super R, ? extends V> after);
    // Note: no compose (would need a function returning two values)
}

// Examples
BiFunction<String, String, String> concat = String::concat;
BiFunction<Integer, Integer, Integer> add = Integer::sum;
BiFunction<String, Integer, String> repeat = String::repeat;  // Java 11

// andThen
BiFunction<Integer, Integer, Integer> addThenDouble =
    add.andThen(x -> x * 2);
addThenDouble.apply(3, 4);  // 14

// Usage with Map.merge
Map<String, Integer> wordCount = new HashMap<>();
wordCount.merge("hello", 1, Integer::sum);  // BiFunction<Integer, Integer, Integer>

// Map.replaceAll
Map<String, String> map = new HashMap<>();
map.put("key", "value");
map.replaceAll((k, v) -> v.toUpperCase());  // BiFunction<String, String, String>
```

#### BiPredicate<T, U> - Takes T and U, returns boolean

```java
@FunctionalInterface
public interface BiPredicate<T, U> {
    boolean test(T t, U u);

    default BiPredicate<T, U> and(BiPredicate<? super T, ? super U> other);
    default BiPredicate<T, U> or(BiPredicate<? super T, ? super U> other);
    default BiPredicate<T, U> negate();
}

// Examples
BiPredicate<String, Integer> longerThan = (s, len) -> s.length() > len;
BiPredicate<String, String> contains = String::contains;

BiPredicate<String, Integer> shorterThan = (s, len) -> s.length() < len;
BiPredicate<String, Integer> between3And10 = longerThan.and(shorterThan);
// Wait - this doesn't work because and() requires same types
// Correct:
BiPredicate<String, Integer> lengthBetween = (s, len) -> s.length() > 3 && s.length() < len;
```

#### BiConsumer<T, U> - Takes T and U, returns void

```java
@FunctionalInterface
public interface BiConsumer<T, U> {
    void accept(T t, U u);

    default BiConsumer<T, U> andThen(BiConsumer<? super T, ? super U> after);
}

// Examples
BiConsumer<String, Integer> printEntry = (k, v) -> System.out.println(k + "=" + v);
BiConsumer<Map<String, Integer>, String> addToMap = (map, key) -> map.merge(key, 1, Integer::sum);

// Usage with Map.forEach
Map<String, Integer> scores = Map.of("Alice", 95, "Bob", 87);
scores.forEach((k, v) -> System.out.println(k + ": " + v));  // BiConsumer
```

#### UnaryOperator<T> - Takes T, returns T (extends Function<T, T>)

```java
@FunctionalInterface
public interface UnaryOperator<T> extends Function<T, T> {
    // Inherits: apply, compose, andThen
    static <T> UnaryOperator<T> identity();
}

// Examples
UnaryOperator<String> toUpper = String::toUpperCase;
UnaryOperator<String> trim = String::trim;
UnaryOperator<Integer> doubler = x -> x * 2;
UnaryOperator<List<String>> sort = list -> {
    list.sort(null);
    return list;
};

// Chaining
UnaryOperator<String> process = ((UnaryOperator<String>) String::trim)
    .andThen(String::toUpperCase)::apply;
// Or cleaner:
Function<String, String> pipeline = trim.andThen(toUpper);

// Usage with List.replaceAll
List<String> names = new ArrayList<>(List.of("alice", "bob"));
names.replaceAll(String::toUpperCase);  // UnaryOperator<String>
// names = ["ALICE", "BOB"]

// Usage with Stream.iterate
Stream.iterate(1, x -> x * 2).limit(10);  // UnaryOperator as second arg
```

#### BinaryOperator<T> - Takes T and T, returns T (extends BiFunction<T, T, T>)

```java
@FunctionalInterface
public interface BinaryOperator<T> extends BiFunction<T, T, T> {
    // Inherits: apply, andThen

    static <T> BinaryOperator<T> minBy(Comparator<? super T> comparator);
    static <T> BinaryOperator<T> maxBy(Comparator<? super T> comparator);
}

// Examples
BinaryOperator<Integer> add = Integer::sum;
BinaryOperator<Integer> max = Integer::max;
BinaryOperator<String> longerString = (a, b) -> a.length() >= b.length() ? a : b;

// minBy / maxBy
BinaryOperator<String> shorter = BinaryOperator.minBy(Comparator.comparingInt(String::length));
shorter.apply("hello", "hi");  // "hi"

BinaryOperator<Employee> highestPaid = BinaryOperator.maxBy(
    Comparator.comparingDouble(Employee::getSalary)
);

// Usage with reduce
List<Integer> numbers = List.of(1, 2, 3, 4, 5);
int sum = numbers.stream().reduce(0, Integer::sum);  // BinaryOperator
Optional<Integer> maxVal = numbers.stream().reduce(Integer::max);
```

#### Primitive Specializations (avoid autoboxing)

```java
// IntPredicate, LongPredicate, DoublePredicate
IntPredicate isEven = n -> n % 2 == 0;
IntPredicate isPositive = n -> n > 0;
IntPredicate evenAndPositive = isEven.and(isPositive);

// IntFunction<R>, LongFunction<R>, DoubleFunction<R>
IntFunction<String> intToString = Integer::toString;

// IntConsumer, LongConsumer, DoubleConsumer
IntConsumer printInt = System.out::println;

// IntSupplier, LongSupplier, DoubleSupplier
IntSupplier randomInt = () -> ThreadLocalRandom.current().nextInt();

// IntUnaryOperator, LongUnaryOperator, DoubleUnaryOperator
IntUnaryOperator negate = x -> -x;
IntUnaryOperator square = x -> x * x;

// IntBinaryOperator, LongBinaryOperator, DoubleBinaryOperator
IntBinaryOperator intAdd = Integer::sum;

// ToIntFunction<T>, ToLongFunction<T>, ToDoubleFunction<T>
ToIntFunction<String> stringLen = String::length;

// ObjIntConsumer<T>, ObjLongConsumer<T>, ObjDoubleConsumer<T>
ObjIntConsumer<List<Integer>> addAtIndex = (list, val) -> list.add(val);
```

### Custom Functional Interfaces

```java
// Tri-function (not in standard library)
@FunctionalInterface
public interface TriFunction<A, B, C, R> {
    R apply(A a, B b, C c);

    default <V> TriFunction<A, B, C, V> andThen(Function<? super R, ? extends V> after) {
        Objects.requireNonNull(after);
        return (a, b, c) -> after.apply(apply(a, b, c));
    }
}

// Checked function (wraps checked exceptions)
@FunctionalInterface
public interface ThrowingFunction<T, R, E extends Exception> {
    R apply(T t) throws E;

    static <T, R> Function<T, R> unchecked(ThrowingFunction<T, R, ?> f) {
        return t -> {
            try {
                return f.apply(t);
            } catch (Exception e) {
                throw new RuntimeException(e);
            }
        };
    }
}

// Usage
List<URL> urls = paths.stream()
    .map(ThrowingFunction.unchecked(URL::new))  // URL constructor throws
    .collect(Collectors.toList());

// Builder callback
@FunctionalInterface
public interface Configurer<T> {
    void configure(T target);

    default Configurer<T> andThen(Configurer<T> after) {
        return target -> { configure(target); after.configure(target); };
    }
}

// Usage in builder pattern
public class ServerBuilder {
    public ServerBuilder configure(Configurer<ServerConfig> configurer) {
        configurer.configure(this.config);
        return this;
    }
}
server.configure(config -> config.setPort(8080))
      .configure(config -> config.setTimeout(30));
```

---

## 3. Stream API (Complete Coverage)

### Stream Creation

```java
// 1. From Collection
List<String> list = List.of("a", "b", "c");
Stream<String> s1 = list.stream();
Stream<String> s2 = list.parallelStream();

// 2. Stream.of() - varargs
Stream<String> s3 = Stream.of("a", "b", "c");
Stream<Integer> s4 = Stream.of(1, 2, 3);

// 3. Arrays.stream()
int[] arr = {1, 2, 3, 4, 5};
IntStream s5 = Arrays.stream(arr);
IntStream s6 = Arrays.stream(arr, 1, 4);  // indices 1 to 3 (exclusive end)
Stream<String> s7 = Arrays.stream(new String[]{"a", "b"});

// 4. Stream.generate() - infinite, unordered
Stream<Double> randoms = Stream.generate(Math::random);  // infinite!
Stream<String> constants = Stream.generate(() -> "hello");

// 5. Stream.iterate() - infinite, ordered
Stream<Integer> evens = Stream.iterate(0, x -> x + 2);  // 0, 2, 4, 6, ...
// With predicate (Java 9) - bounded
Stream<Integer> evensTo100 = Stream.iterate(0, x -> x <= 100, x -> x + 2);

// 6. IntStream.range / rangeClosed
IntStream range = IntStream.range(0, 10);        // 0 to 9
IntStream rangeClosed = IntStream.rangeClosed(1, 10);  // 1 to 10

// 7. From String
IntStream chars = "hello".chars();  // IntStream of char values

// 8. From file
Stream<String> lines = Files.lines(Path.of("file.txt"));  // lazy, must close

// 9. Stream.empty()
Stream<String> empty = Stream.empty();

// 10. Stream.concat()
Stream<String> combined = Stream.concat(stream1, stream2);

// 11. From Map
Stream<Map.Entry<String, Integer>> entries = map.entrySet().stream();
Stream<String> keys = map.keySet().stream();
Stream<Integer> values = map.values().stream();

// 12. Stream.ofNullable (Java 9) - 0 or 1 element
Stream<String> maybeStream = Stream.ofNullable(getNullableValue());

// 13. Pattern splitting
Stream<String> words = Pattern.compile("\\s+").splitAsStream("hello world foo");

// 14. Builder
Stream<String> built = Stream.<String>builder()
    .add("a").add("b").add("c")
    .build();
```

### Intermediate Operations (Lazy - not executed until terminal op)

```java
List<Employee> employees = getEmployees();

// filter(Predicate<T>) - keep elements matching predicate
Stream<Employee> seniors = employees.stream()
    .filter(e -> e.getAge() > 50);

// map(Function<T, R>) - transform each element
Stream<String> names = employees.stream()
    .map(Employee::getName);

// mapToInt / mapToLong / mapToDouble - avoids boxing
IntStream ages = employees.stream()
    .mapToInt(Employee::getAge);
double avgSalary = employees.stream()
    .mapToDouble(Employee::getSalary)
    .average()
    .orElse(0.0);

// flatMap(Function<T, Stream<R>>) - one-to-many, flattens nested streams
List<List<String>> nested = List.of(List.of("a", "b"), List.of("c", "d"));
Stream<String> flat = nested.stream()
    .flatMap(Collection::stream);  // ["a", "b", "c", "d"]

// flatMap with Optional streams
Stream<String> validNames = employees.stream()
    .map(Employee::getMiddleName)        // Stream<Optional<String>>
    .flatMap(Optional::stream);          // Stream<String> - only present values

// flatMapToInt / flatMapToLong / flatMapToDouble
IntStream allScores = students.stream()
    .flatMapToInt(s -> Arrays.stream(s.getScores()));

// distinct() - removes duplicates (uses equals/hashCode)
Stream<String> unique = names.stream().distinct();

// sorted() - natural order (elements must be Comparable)
Stream<String> sorted = names.stream().sorted();

// sorted(Comparator) - custom order
Stream<Employee> bySalary = employees.stream()
    .sorted(Comparator.comparingDouble(Employee::getSalary).reversed());

// Multi-level sort
Stream<Employee> multiSort = employees.stream()
    .sorted(Comparator.comparing(Employee::getDepartment)
        .thenComparing(Employee::getSalary, Comparator.reverseOrder()));

// peek(Consumer<T>) - for debugging, doesn't alter stream
Stream<String> peeked = names.stream()
    .filter(n -> n.length() > 3)
    .peek(n -> System.out.println("Filtered: " + n))
    .map(String::toUpperCase)
    .peek(n -> System.out.println("Mapped: " + n));

// limit(long n) - take first n elements (short-circuits)
Stream<Integer> firstFive = Stream.iterate(1, x -> x + 1).limit(5);

// skip(long n) - skip first n elements
Stream<Employee> afterFirst10 = employees.stream().skip(10);

// Pagination pattern
List<Employee> page = employees.stream()
    .skip((pageNumber - 1) * pageSize)
    .limit(pageSize)
    .toList();

// takeWhile(Predicate) - Java 9 - takes while predicate is true, then stops
Stream<Integer> lessThan5 = Stream.of(1, 2, 3, 5, 4, 2)
    .takeWhile(x -> x < 5);  // [1, 2, 3] - stops at 5, doesn't see 4, 2

// dropWhile(Predicate) - Java 9 - drops while predicate is true, takes rest
Stream<Integer> fromFive = Stream.of(1, 2, 3, 5, 4, 2)
    .dropWhile(x -> x < 5);  // [5, 4, 2]

// mapMulti (Java 16) - imperative alternative to flatMap
Stream<Integer> expanded = Stream.of(1, 2, 3)
    .<Integer>mapMulti((elem, consumer) -> {
        consumer.accept(elem);
        consumer.accept(elem * 10);
    });  // [1, 10, 2, 20, 3, 30]
```

### Terminal Operations (Trigger processing)

```java
// forEach(Consumer<T>) - perform action on each element
employees.stream()
    .filter(e -> e.getSalary() > 100000)
    .forEach(e -> System.out.println(e.getName()));

// forEachOrdered(Consumer<T>) - respects encounter order in parallel streams
employees.parallelStream()
    .forEachOrdered(System.out::println);  // maintains order

// collect(Collector<T, A, R>) - mutable reduction
List<String> nameList = employees.stream()
    .map(Employee::getName)
    .collect(Collectors.toList());

// collect(Supplier, BiConsumer, BiConsumer) - manual collector
List<String> manual = stream.collect(
    ArrayList::new,       // supplier
    ArrayList::add,       // accumulator
    ArrayList::addAll     // combiner (for parallel)
);

// reduce - immutable reduction
// reduce(identity, accumulator)
int sum = List.of(1, 2, 3, 4, 5).stream().reduce(0, Integer::sum);  // 15
String joined = List.of("a", "b", "c").stream().reduce("", String::concat);  // "abc"

// reduce(accumulator) - returns Optional (stream might be empty)
Optional<Integer> max = numbers.stream().reduce(Integer::max);

// reduce(identity, accumulator, combiner) - for parallel streams with type change
int totalLength = strings.parallelStream().reduce(
    0,                              // identity
    (length, str) -> length + str.length(),  // accumulator
    Integer::sum                    // combiner
);

// count() - returns long
long count = employees.stream()
    .filter(e -> e.getDepartment().equals("Engineering"))
    .count();

// min(Comparator) / max(Comparator) - returns Optional
Optional<Employee> youngest = employees.stream()
    .min(Comparator.comparingInt(Employee::getAge));
Optional<Employee> highestPaid = employees.stream()
    .max(Comparator.comparingDouble(Employee::getSalary));

// anyMatch(Predicate) - true if any element matches (short-circuits)
boolean hasManager = employees.stream()
    .anyMatch(e -> e.getRole().equals("Manager"));

// allMatch(Predicate) - true if all elements match (short-circuits on false)
boolean allAdults = employees.stream()
    .allMatch(e -> e.getAge() >= 18);

// noneMatch(Predicate) - true if no elements match (short-circuits on true)
boolean noInterns = employees.stream()
    .noneMatch(e -> e.getRole().equals("Intern"));

// findFirst() - returns Optional of first element (deterministic)
Optional<Employee> first = employees.stream()
    .filter(e -> e.getSalary() > 150000)
    .findFirst();

// findAny() - returns Optional of any element (non-deterministic, faster in parallel)
Optional<Employee> any = employees.parallelStream()
    .filter(e -> e.getDepartment().equals("Sales"))
    .findAny();

// toArray() - returns Object[]
Object[] array = stream.toArray();

// toArray(IntFunction) - returns typed array
String[] nameArray = employees.stream()
    .map(Employee::getName)
    .toArray(String[]::new);

// toList() - Java 16 - unmodifiable list (preferred over collect(Collectors.toList()))
List<String> immutableNames = employees.stream()
    .map(Employee::getName)
    .toList();

// Primitive stream terminal ops
IntStream intStream = IntStream.rangeClosed(1, 100);
int sum2 = intStream.sum();  // 5050
OptionalInt max2 = IntStream.of(3, 1, 4).max();
OptionalDouble avg = IntStream.of(1, 2, 3).average();
IntSummaryStatistics stats = employees.stream()
    .mapToInt(Employee::getAge)
    .summaryStatistics();
// stats.getMax(), getMin(), getAverage(), getSum(), getCount()
```

### Collectors (java.util.stream.Collectors)

```java
import static java.util.stream.Collectors.*;

List<Employee> employees = getEmployees();

// toList() - mutable ArrayList
List<String> names = employees.stream().map(Employee::getName).collect(toList());

// toUnmodifiableList() - Java 10
List<String> immutable = employees.stream().map(Employee::getName).collect(toUnmodifiableList());

// toSet() - HashSet
Set<String> departments = employees.stream().map(Employee::getDepartment).collect(toSet());

// toUnmodifiableSet() - Java 10
Set<String> immutableDepts = employees.stream().map(Employee::getDepartment).collect(toUnmodifiableSet());

// toCollection(Supplier) - specific collection type
TreeSet<String> sortedNames = employees.stream()
    .map(Employee::getName)
    .collect(toCollection(TreeSet::new));
LinkedList<Employee> linked = employees.stream().collect(toCollection(LinkedList::new));

// toMap(keyMapper, valueMapper)
Map<Integer, String> idToName = employees.stream()
    .collect(toMap(Employee::getId, Employee::getName));
// Throws IllegalStateException on duplicate keys!

// toMap with merge function (handle duplicates)
Map<String, Employee> deptToHighestPaid = employees.stream()
    .collect(toMap(
        Employee::getDepartment,
        Function.identity(),
        BinaryOperator.maxBy(Comparator.comparingDouble(Employee::getSalary))
    ));

// toMap with merge function and map supplier
Map<String, Integer> nameToAge = employees.stream()
    .collect(toMap(
        Employee::getName,
        Employee::getAge,
        (existing, replacement) -> existing,  // keep first on collision
        LinkedHashMap::new                     // maintain insertion order
    ));

// toUnmodifiableMap() - Java 10
Map<Integer, String> immutableMap = employees.stream()
    .collect(toUnmodifiableMap(Employee::getId, Employee::getName));

// toConcurrentMap - thread-safe for parallel streams
ConcurrentMap<String, List<Employee>> concurrent = employees.parallelStream()
    .collect(toConcurrentMap(
        Employee::getDepartment,
        e -> new ArrayList<>(List.of(e)),
        (a, b) -> { a.addAll(b); return a; }
    ));

// groupingBy(classifier) - groups into Map<K, List<T>>
Map<String, List<Employee>> byDept = employees.stream()
    .collect(groupingBy(Employee::getDepartment));

// groupingBy with downstream collector
Map<String, Long> countByDept = employees.stream()
    .collect(groupingBy(Employee::getDepartment, counting()));

Map<String, Double> avgSalaryByDept = employees.stream()
    .collect(groupingBy(
        Employee::getDepartment,
        averagingDouble(Employee::getSalary)
    ));

Map<String, Optional<Employee>> highestPaidByDept = employees.stream()
    .collect(groupingBy(
        Employee::getDepartment,
        maxBy(Comparator.comparingDouble(Employee::getSalary))
    ));

Map<String, List<String>> namesByDept = employees.stream()
    .collect(groupingBy(
        Employee::getDepartment,
        mapping(Employee::getName, toList())
    ));

// groupingBy with map factory (control map type)
TreeMap<String, List<Employee>> sortedByDept = employees.stream()
    .collect(groupingBy(Employee::getDepartment, TreeMap::new, toList()));

// Multi-level grouping
Map<String, Map<String, List<Employee>>> byDeptAndRole = employees.stream()
    .collect(groupingBy(
        Employee::getDepartment,
        groupingBy(Employee::getRole)
    ));

// partitioningBy(predicate) - splits into Map<Boolean, List<T>>
Map<Boolean, List<Employee>> seniorVsJunior = employees.stream()
    .collect(partitioningBy(e -> e.getExperience() > 5));
List<Employee> seniors = seniorVsJunior.get(true);
List<Employee> juniors = seniorVsJunior.get(false);

// partitioningBy with downstream
Map<Boolean, Long> countSeniorVsJunior = employees.stream()
    .collect(partitioningBy(e -> e.getExperience() > 5, counting()));

// joining() - concatenates strings
String allNames = employees.stream()
    .map(Employee::getName)
    .collect(joining());  // "AliceBobCharlie"

String csv = employees.stream()
    .map(Employee::getName)
    .collect(joining(", "));  // "Alice, Bob, Charlie"

String formatted = employees.stream()
    .map(Employee::getName)
    .collect(joining(", ", "[", "]"));  // "[Alice, Bob, Charlie]"

// counting()
Long total = employees.stream().collect(counting());  // prefer .count()

// summarizingInt / summarizingDouble / summarizingLong
IntSummaryStatistics ageSummary = employees.stream()
    .collect(summarizingInt(Employee::getAge));
// ageSummary.getAverage(), getMax(), getMin(), getSum(), getCount()

DoubleSummaryStatistics salaryStats = employees.stream()
    .collect(summarizingDouble(Employee::getSalary));

// averagingInt / averagingDouble / averagingLong
Double avgAge = employees.stream().collect(averagingInt(Employee::getAge));

// summingInt / summingDouble / summingLong
Integer totalAge = employees.stream().collect(summingInt(Employee::getAge));

// reducing (collector version of stream.reduce)
Optional<Employee> highestPaid2 = employees.stream()
    .collect(reducing(BinaryOperator.maxBy(
        Comparator.comparingDouble(Employee::getSalary)
    )));

Integer totalSalary = employees.stream()
    .collect(reducing(0, Employee::getAge, Integer::sum));

// collectingAndThen - transform collector result
List<Employee> unmodifiable = employees.stream()
    .collect(collectingAndThen(toList(), Collections::unmodifiableList));

Double avgOrZero = employees.stream()
    .collect(collectingAndThen(
        averagingDouble(Employee::getSalary),
        avg -> avg == null ? 0.0 : avg
    ));

// Get single result or throw
Employee single = employees.stream()
    .filter(e -> e.getId() == 42)
    .collect(collectingAndThen(toList(), list -> {
        if (list.size() != 1) throw new IllegalStateException("Expected 1, got " + list.size());
        return list.get(0);
    }));

// mapping(Function, downstream) - applies mapping before collecting
Map<String, Set<String>> rolesByDept = employees.stream()
    .collect(groupingBy(
        Employee::getDepartment,
        mapping(Employee::getRole, toSet())
    ));

// flatMapping (Java 9)
Map<String, Set<String>> skillsByDept = employees.stream()
    .collect(groupingBy(
        Employee::getDepartment,
        flatMapping(e -> e.getSkills().stream(), toSet())
    ));

// filtering (Java 9) - filter within group
Map<String, List<Employee>> highPaidByDept = employees.stream()
    .collect(groupingBy(
        Employee::getDepartment,
        filtering(e -> e.getSalary() > 100000, toList())
    ));
// Difference from filter().collect(groupingBy()): keeps empty lists for depts with no high-paid

// teeing (Java 12) - applies two collectors and merges results
var result = employees.stream().collect(
    teeing(
        minBy(Comparator.comparingDouble(Employee::getSalary)),
        maxBy(Comparator.comparingDouble(Employee::getSalary)),
        (min, max) -> Map.of("lowest", min.orElseThrow(), "highest", max.orElseThrow())
    )
);
```

### Parallel Streams

```java
// Creation
Stream<Employee> parallel1 = employees.parallelStream();
Stream<Employee> parallel2 = employees.stream().parallel();
Stream<Employee> sequential = parallel1.sequential();  // convert back

// Check if parallel
boolean isParallel = stream.isParallel();

// When to use parallel streams:
// - Large data sets (>10,000 elements generally)
// - CPU-intensive operations per element
// - No shared mutable state
// - Source supports efficient splitting (ArrayList, arrays > LinkedList)
// - Operation is associative and stateless

// When NOT to use:
// - Small data sets (overhead > benefit)
// - I/O operations (blocks ForkJoinPool threads)
// - Order-dependent operations (findFirst, limit with sorted)
// - Operations with shared mutable state
// - LinkedList or Iterator-based sources (poor split)

// ForkJoinPool - parallel streams use common pool by default
// Common pool size = Runtime.getRuntime().availableProcessors() - 1

// Custom ForkJoinPool for isolation
ForkJoinPool customPool = new ForkJoinPool(4);
List<String> result = customPool.submit(() ->
    employees.parallelStream()
        .filter(e -> e.getSalary() > 100000)
        .map(Employee::getName)
        .collect(Collectors.toList())
).get();
customPool.shutdown();

// Thread-safe collectors for parallel streams
// toList(), toSet() - already thread-safe
// toConcurrentMap - better than toMap for parallel
// groupingByConcurrent - better than groupingBy for parallel

Map<String, List<Employee>> concurrentGrouping = employees.parallelStream()
    .collect(groupingByConcurrent(Employee::getDepartment));

// Pitfalls
// 1. Shared mutable state - WRONG
List<Integer> unsafeList = new ArrayList<>();
IntStream.range(0, 1000).parallel().forEach(unsafeList::add);  // Race condition!

// Correct: use collect
List<Integer> safeList = IntStream.range(0, 1000).parallel()
    .boxed()
    .collect(Collectors.toList());

// 2. Side effects in forEach - order not guaranteed
employees.parallelStream()
    .forEach(e -> System.out.println(e.getName()));  // random order

// 3. reduce with non-associative operation - WRONG
// Subtraction is not associative: (a-b)-c != a-(b-c)
int wrong = List.of(1, 2, 3, 4).parallelStream()
    .reduce(0, (a, b) -> a - b);  // unpredictable result

// 4. Stateful intermediate operations in parallel
// sorted(), distinct() - work but have performance cost
// limit(), skip() - expensive in parallel (need coordination)

// 5. Blocking ForkJoinPool common pool
// If one parallel stream blocks on I/O, it affects ALL parallel streams in the JVM
employees.parallelStream()
    .map(e -> httpClient.fetch(e.getUrl()))  // TERRIBLE - blocks shared pool
    .collect(toList());

// Performance tip: unordered() hint
long count = hugeList.parallelStream()
    .unordered()  // allows more optimization
    .distinct()
    .count();
```

### Complete Stream Examples

```java
// Example 1: Word Frequency Counter
public Map<String, Long> wordFrequency(String text) {
    return Arrays.stream(text.toLowerCase().split("\\W+"))
        .filter(word -> !word.isEmpty())
        .collect(Collectors.groupingBy(
            Function.identity(),
            Collectors.counting()
        ));
}

// Top N words
public List<Map.Entry<String, Long>> topNWords(String text, int n) {
    return wordFrequency(text).entrySet().stream()
        .sorted(Map.Entry.<String, Long>comparingByValue().reversed())
        .limit(n)
        .collect(Collectors.toList());
}

// Example 2: Group Employees by Department with Statistics
public Map<String, DoubleSummaryStatistics> salaryStatsByDept(List<Employee> employees) {
    return employees.stream()
        .collect(Collectors.groupingBy(
            Employee::getDepartment,
            Collectors.summarizingDouble(Employee::getSalary)
        ));
}

// Department report: name, count, avg salary, highest paid person
public record DeptReport(String dept, long count, double avgSalary, String highestPaid) {}

public List<DeptReport> departmentReports(List<Employee> employees) {
    return employees.stream()
        .collect(Collectors.groupingBy(Employee::getDepartment))
        .entrySet().stream()
        .map(entry -> new DeptReport(
            entry.getKey(),
            entry.getValue().size(),
            entry.getValue().stream().mapToDouble(Employee::getSalary).average().orElse(0),
            entry.getValue().stream()
                .max(Comparator.comparingDouble(Employee::getSalary))
                .map(Employee::getName).orElse("N/A")
        ))
        .sorted(Comparator.comparing(DeptReport::avgSalary).reversed())
        .toList();
}

// Example 3: Flatten Nested Lists and Process
public record Order(String customerId, List<LineItem> items) {}
public record LineItem(String product, int quantity, double price) {}

// Total revenue per customer
public Map<String, Double> revenueByCustomer(List<Order> orders) {
    return orders.stream()
        .collect(Collectors.groupingBy(
            Order::customerId,
            Collectors.flatMapping(
                order -> order.items().stream(),
                Collectors.summingDouble(item -> item.quantity() * item.price())
            )
        ));
}

// All unique products ordered
public Set<String> allProducts(List<Order> orders) {
    return orders.stream()
        .flatMap(order -> order.items().stream())
        .map(LineItem::product)
        .collect(Collectors.toSet());
}

// Example 4: Complex Filtering and Transformation
public record Transaction(String id, String type, double amount, LocalDate date, String status) {}

public Map<String, List<Transaction>> getMonthlyHighValueTransactions(
        List<Transaction> transactions, double threshold) {
    return transactions.stream()
        .filter(t -> t.status().equals("COMPLETED"))
        .filter(t -> t.amount() > threshold)
        .sorted(Comparator.comparing(Transaction::date).reversed())
        .collect(Collectors.groupingBy(
            t -> t.date().getMonth().toString(),
            LinkedHashMap::new,  // maintain month order
            Collectors.toList()
        ));
}

// Example 5: Matrix Operations with Streams
public int[][] transposeMatrix(int[][] matrix) {
    return IntStream.range(0, matrix[0].length)
        .mapToObj(col -> IntStream.range(0, matrix.length)
            .map(row -> matrix[row][col])
            .toArray())
        .toArray(int[][]::new);
}

// Example 6: Cartesian Product
public <T, U> List<Map.Entry<T, U>> cartesianProduct(List<T> list1, List<U> list2) {
    return list1.stream()
        .flatMap(item1 -> list2.stream()
            .map(item2 -> Map.entry(item1, item2)))
        .toList();
}

// Example 7: Running/Cumulative Sum
public List<Integer> cumulativeSum(List<Integer> numbers) {
    AtomicInteger running = new AtomicInteger(0);
    return numbers.stream()
        .map(running::addAndGet)
        .toList();
    // Note: not safe for parallel streams - use sequential only
}

// Better approach for cumulative operations:
public int[] cumulativeSum(int[] arr) {
    return Arrays.stream(arr)
        .reduce(new int[arr.length], (result, val) -> result, (a, b) -> a);
    // Actually, prefix sum is better done imperatively
    // Streams aren't ideal for stateful cumulative operations
}
```

---

## 4. Optional<T>

### Creation

```java
// of(value) - throws NullPointerException if value is null
Optional<String> opt1 = Optional.of("hello");
Optional<String> opt2 = Optional.of(null);  // NPE!

// ofNullable(value) - empty if null, present if non-null
Optional<String> opt3 = Optional.ofNullable(getString());  // may be empty
Optional<String> opt4 = Optional.ofNullable(null);  // Optional.empty()

// empty() - explicitly empty Optional
Optional<String> opt5 = Optional.empty();
```

### All Methods

```java
Optional<String> opt = Optional.of("hello");
Optional<String> empty = Optional.empty();

// isPresent() - true if value present
if (opt.isPresent()) { /* ... */ }

// isEmpty() - Java 11 - true if empty
if (empty.isEmpty()) { /* ... */ }

// get() - returns value or throws NoSuchElementException
String val = opt.get();  // "hello"
// String bad = empty.get();  // NoSuchElementException - AVOID get() without check

// orElse(defaultValue) - returns value or default (default always evaluated)
String result = empty.orElse("default");  // "default"
String result2 = opt.orElse("default");   // "hello"
// WARNING: orElse evaluates its argument even when Optional is present
String result3 = opt.orElse(expensiveOperation());  // expensiveOperation() ALWAYS called

// orElseGet(Supplier) - returns value or computes default (lazy)
String result4 = empty.orElseGet(() -> computeDefault());  // only called if empty
String result5 = opt.orElseGet(() -> computeDefault());    // NOT called

// orElseThrow() - Java 10 - throws NoSuchElementException (preferred over get())
String val2 = opt.orElseThrow();  // same as get() but more readable intent

// orElseThrow(Supplier<Exception>) - throws custom exception
String val3 = opt.orElseThrow(() -> new NotFoundException("Value not found"));
Employee emp = findById(id).orElseThrow(() ->
    new EntityNotFoundException("Employee not found: " + id));

// map(Function) - transforms value if present, returns Optional
Optional<Integer> length = opt.map(String::length);  // Optional[5]
Optional<Integer> emptyLen = empty.map(String::length);  // Optional.empty()

// Chaining maps
Optional<String> city = employee
    .map(Employee::getAddress)
    .map(Address::getCity);

// flatMap(Function<T, Optional<U>>) - when mapper returns Optional (avoids Optional<Optional<>>)
Optional<String> flatMapped = opt.flatMap(s -> s.isEmpty() ? Optional.empty() : Optional.of(s.toUpperCase()));

// Without flatMap: Optional<Optional<Address>> - nested!
// With flatMap: Optional<Address>
Optional<String> city2 = findEmployee(id)
    .flatMap(Employee::getAddress)  // getAddress returns Optional<Address>
    .flatMap(Address::getCity);     // getCity returns Optional<String>

// filter(Predicate) - keeps value only if predicate matches
Optional<String> filtered = opt.filter(s -> s.length() > 3);  // Optional["hello"]
Optional<String> filteredOut = opt.filter(s -> s.length() > 10);  // Optional.empty()

// ifPresent(Consumer) - execute action if present
opt.ifPresent(System.out::println);  // prints "hello"
empty.ifPresent(System.out::println);  // does nothing

// ifPresentOrElse(Consumer, Runnable) - Java 9
opt.ifPresentOrElse(
    value -> System.out.println("Found: " + value),
    () -> System.out.println("Not found")
);

// or(Supplier<Optional>) - Java 9 - provides alternative Optional
Optional<String> result6 = empty.or(() -> Optional.of("fallback"));  // Optional["fallback"]
Optional<String> result7 = opt.or(() -> Optional.of("fallback"));    // Optional["hello"]

// Chaining or() for cascading lookups
Optional<Config> config = loadFromCache(key)
    .or(() -> loadFromDatabase(key))
    .or(() -> loadFromRemote(key))
    .or(() -> Optional.of(defaultConfig()));

// stream() - Java 9 - converts to 0 or 1 element stream
Stream<String> stream = opt.stream();  // Stream of "hello"
Stream<String> emptyStream = empty.stream();  // empty stream

// Useful for flatMapping a stream of Optionals
List<Optional<String>> optionals = List.of(Optional.of("a"), Optional.empty(), Optional.of("b"));
List<String> values = optionals.stream()
    .flatMap(Optional::stream)
    .toList();  // ["a", "b"]
```

### Best Practices

```java
// DO: Use Optional for method return types that might have no result
public Optional<Employee> findById(Long id) {
    return Optional.ofNullable(repository.findById(id));
}

// DO: Use with streams for optional transformations
public Optional<String> getManagerName(Long employeeId) {
    return findById(employeeId)
        .flatMap(Employee::getManager)
        .map(Employee::getName);
}

// DO: Use orElseGet for expensive defaults
public Employee getOrCreateDefault(Long id) {
    return findById(id).orElseGet(() -> createDefaultEmployee());
}

// DO: Use in service layer for null safety
public class OrderService {
    public Optional<OrderSummary> getOrderSummary(String orderId) {
        return orderRepository.findById(orderId)
            .filter(order -> order.getStatus() != Status.CANCELLED)
            .map(order -> new OrderSummary(
                order.getId(),
                order.getTotal(),
                order.getItems().size()
            ));
    }
}
```

### Anti-Patterns (DO NOT DO)

```java
// DON'T: Use Optional as a field
class Employee {
    Optional<String> middleName;  // BAD - not serializable, overhead
    String middleName;  // GOOD - can be null
}

// DON'T: Use Optional as a method parameter
public void process(Optional<String> name) { }  // BAD
public void process(String name) { }  // GOOD - caller passes null or overloads

// DON'T: Use Optional in collections
List<Optional<String>> names;  // BAD
List<String> names;  // GOOD - just filter nulls

// DON'T: Use Optional.get() without checking
String name = optional.get();  // BAD - can throw
String name = optional.orElseThrow();  // slightly better (clearer intent)
String name = optional.orElse("default");  // BEST

// DON'T: Use Optional for primitive types (use OptionalInt/Long/Double)
Optional<Integer> count;      // BAD - boxing overhead
OptionalInt count;             // GOOD

// DON'T: Use isPresent() + get() pattern
if (opt.isPresent()) {
    return opt.get();  // BAD - imperative style
}
return opt.orElse(default);  // GOOD - functional style

// DON'T: Return null from a method declared to return Optional
public Optional<String> find() {
    return null;  // TERRIBLE - defeats the purpose
    return Optional.empty();  // CORRECT
}

// DON'T: Wrap and immediately unwrap
Optional.ofNullable(value).orElse(null);  // pointless

// DON'T: Use Optional.of() when value might be null
Optional.of(possiblyNull);  // BAD - NPE
Optional.ofNullable(possiblyNull);  // GOOD

// DON'T: Nested Optional operations when map/flatMap suffices
if (opt.isPresent()) {
    Optional<Address> addr = opt.get().getAddress();
    if (addr.isPresent()) {
        return addr.get().getCity();
    }
}
// INSTEAD:
return opt.flatMap(Employee::getAddress).map(Address::getCity);
```

---

## 5. New Date/Time API (java.time)

### Core Classes

```java
import java.time.*;
import java.time.format.*;
import java.time.temporal.*;

// LocalDate - date without time or timezone
LocalDate today = LocalDate.now();
LocalDate specific = LocalDate.of(2024, 3, 15);  // 2024-03-15
LocalDate parsed = LocalDate.parse("2024-03-15");
LocalDate fromMonth = LocalDate.of(2024, Month.MARCH, 15);

// LocalTime - time without date or timezone
LocalTime now = LocalTime.now();
LocalTime specific2 = LocalTime.of(14, 30, 0);  // 14:30:00
LocalTime parsed2 = LocalTime.parse("14:30:00");
LocalTime noon = LocalTime.NOON;
LocalTime midnight = LocalTime.MIDNIGHT;

// LocalDateTime - date + time without timezone
LocalDateTime nowDT = LocalDateTime.now();
LocalDateTime specific3 = LocalDateTime.of(2024, 3, 15, 14, 30);
LocalDateTime combined = LocalDateTime.of(today, now);
LocalDateTime parsed3 = LocalDateTime.parse("2024-03-15T14:30:00");

// ZonedDateTime - date + time + timezone (full representation)
ZonedDateTime zonedNow = ZonedDateTime.now();
ZonedDateTime zonedSpecific = ZonedDateTime.of(specific3, ZoneId.of("America/New_York"));
ZonedDateTime utc = ZonedDateTime.now(ZoneId.of("UTC"));
Set<String> allZones = ZoneId.getAvailableZoneIds();

// OffsetDateTime - date + time + UTC offset (for storing in DB)
OffsetDateTime offset = OffsetDateTime.now();
OffsetDateTime withOffset = OffsetDateTime.of(specific3, ZoneOffset.ofHours(5));

// Instant - machine timestamp (epoch seconds + nanos)
Instant instant = Instant.now();
Instant epoch = Instant.EPOCH;  // 1970-01-01T00:00:00Z
Instant fromEpoch = Instant.ofEpochSecond(1700000000);
long epochMillis = instant.toEpochMilli();

// Converting between types
LocalDateTime ldt = LocalDateTime.ofInstant(instant, ZoneId.systemDefault());
ZonedDateTime zdt = instant.atZone(ZoneId.of("Asia/Tokyo"));
Instant back = zdt.toInstant();
```

### Duration and Period

```java
// Duration - time-based amount (hours, minutes, seconds, nanos)
Duration fiveMinutes = Duration.ofMinutes(5);
Duration twoHours = Duration.ofHours(2);
Duration halfSecond = Duration.ofMillis(500);
Duration complex = Duration.ofHours(2).plusMinutes(30);
Duration between = Duration.between(startTime, endTime);

// Duration operations
long seconds = fiveMinutes.getSeconds();   // 300
long millis = fiveMinutes.toMillis();      // 300000
Duration doubled = fiveMinutes.multipliedBy(2);
Duration negated = fiveMinutes.negated();
boolean negative = negated.isNegative();   // true

// Period - date-based amount (years, months, days)
Period oneYear = Period.ofYears(1);
Period twoMonths = Period.ofMonths(2);
Period tenDays = Period.ofDays(10);
Period complex2 = Period.of(1, 2, 15);  // 1 year, 2 months, 15 days
Period between2 = Period.between(startDate, endDate);

// Period operations
int years = complex2.getYears();   // 1
int months = complex2.getMonths(); // 2
int days = complex2.getDays();     // 15
Period normalized = Period.of(0, 15, 0).normalized();  // P1Y3M (15 months = 1yr 3mo)

// Adding duration/period to dates
LocalDateTime later = nowDT.plus(Duration.ofHours(3));
LocalDate futureDate = today.plus(Period.ofMonths(6));
LocalDate nextWeek = today.plusWeeks(1);
LocalTime inAnHour = now.plusHours(1);
```

### Common Operations

```java
// Comparisons
boolean isBefore = date1.isBefore(date2);
boolean isAfter = date1.isAfter(date2);
boolean isEqual = date1.isEqual(date2);

// Extracting components
int year = today.getYear();
Month month = today.getMonth();
int monthValue = today.getMonthValue();
int dayOfMonth = today.getDayOfMonth();
DayOfWeek day = today.getDayOfWeek();
int dayOfYear = today.getDayOfYear();
boolean isLeap = today.isLeapYear();

// Modifying (all immutable - return new instances)
LocalDate nextMonth = today.plusMonths(1);
LocalDate lastYear = today.minusYears(1);
LocalDate withDay = today.withDayOfMonth(1);  // first of this month
LocalDate withMonth = today.withMonth(12);     // December of this year

// TemporalAdjusters - complex date calculations
LocalDate firstDayOfMonth = today.with(TemporalAdjusters.firstDayOfMonth());
LocalDate lastDayOfMonth = today.with(TemporalAdjusters.lastDayOfMonth());
LocalDate firstDayOfYear = today.with(TemporalAdjusters.firstDayOfYear());
LocalDate nextMonday = today.with(TemporalAdjusters.next(DayOfWeek.MONDAY));
LocalDate prevFriday = today.with(TemporalAdjusters.previous(DayOfWeek.FRIDAY));
LocalDate firstMondayOfMonth = today.with(
    TemporalAdjusters.firstInMonth(DayOfWeek.MONDAY));

// Custom adjuster
TemporalAdjuster nextWorkingDay = temporal -> {
    LocalDate date = LocalDate.from(temporal);
    DayOfWeek dow = date.getDayOfWeek();
    if (dow == DayOfWeek.FRIDAY) return date.plusDays(3);
    if (dow == DayOfWeek.SATURDAY) return date.plusDays(2);
    return date.plusDays(1);
};
LocalDate nextWork = today.with(nextWorkingDay);

// ChronoUnit - measuring between dates
long daysBetween = ChronoUnit.DAYS.between(date1, date2);
long hoursBetween = ChronoUnit.HOURS.between(time1, time2);
long monthsBetween = ChronoUnit.MONTHS.between(date1, date2);
```

### DateTimeFormatter

```java
// Predefined formatters
String iso = today.format(DateTimeFormatter.ISO_LOCAL_DATE);  // 2024-03-15
String isoDateTime = nowDT.format(DateTimeFormatter.ISO_LOCAL_DATE_TIME);

// Custom patterns
DateTimeFormatter custom = DateTimeFormatter.ofPattern("dd/MM/yyyy");
String formatted = today.format(custom);  // "15/03/2024"

DateTimeFormatter withTime = DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss");
String formatted2 = nowDT.format(withTime);  // "2024-03-15 14:30:00"

DateTimeFormatter full = DateTimeFormatter.ofPattern("EEEE, MMMM dd, yyyy");
String formatted3 = today.format(full);  // "Friday, March 15, 2024"

// Parsing
LocalDate parsed4 = LocalDate.parse("15/03/2024", custom);
LocalDateTime parsed5 = LocalDateTime.parse("2024-03-15 14:30:00", withTime);

// With locale
DateTimeFormatter german = DateTimeFormatter.ofPattern("dd. MMMM yyyy", Locale.GERMAN);
String germanDate = today.format(german);  // "15. März 2024"

// Builder for complex formats
DateTimeFormatter complex3 = new DateTimeFormatterBuilder()
    .appendText(ChronoField.DAY_OF_WEEK)
    .appendLiteral(", ")
    .appendText(ChronoField.MONTH_OF_YEAR)
    .appendLiteral(" ")
    .appendValue(ChronoField.DAY_OF_MONTH)
    .appendLiteral(", ")
    .appendValue(ChronoField.YEAR)
    .toFormatter();

// Converting to/from legacy Date
Date legacyDate = Date.from(instant);
Instant fromLegacy = legacyDate.toInstant();
LocalDate fromLegacy2 = legacyDate.toInstant()
    .atZone(ZoneId.systemDefault())
    .toLocalDate();

// Calendar to LocalDateTime
Calendar cal = Calendar.getInstance();
LocalDateTime fromCal = LocalDateTime.ofInstant(cal.toInstant(), ZoneId.systemDefault());
```

### Practical Examples

```java
// Calculate age
public int calculateAge(LocalDate birthDate) {
    return Period.between(birthDate, LocalDate.now()).getYears();
}

// Business days between two dates
public long businessDaysBetween(LocalDate start, LocalDate end) {
    return start.datesUntil(end)  // Java 9: Stream<LocalDate>
        .filter(date -> date.getDayOfWeek() != DayOfWeek.SATURDAY
                     && date.getDayOfWeek() != DayOfWeek.SUNDAY)
        .count();
}

// Get all Mondays in a month
public List<LocalDate> getMondaysInMonth(YearMonth yearMonth) {
    return yearMonth.atDay(1).datesUntil(yearMonth.atEndOfMonth().plusDays(1))
        .filter(date -> date.getDayOfWeek() == DayOfWeek.MONDAY)
        .toList();
}

// Is within business hours
public boolean isBusinessHours(LocalDateTime dateTime) {
    LocalTime time = dateTime.toLocalTime();
    DayOfWeek day = dateTime.getDayOfWeek();
    return day != DayOfWeek.SATURDAY
        && day != DayOfWeek.SUNDAY
        && !time.isBefore(LocalTime.of(9, 0))
        && time.isBefore(LocalTime.of(17, 0));
}

// Timezone conversion
public ZonedDateTime convertTimezone(LocalDateTime dateTime, String fromZone, String toZone) {
    ZonedDateTime source = dateTime.atZone(ZoneId.of(fromZone));
    return source.withZoneSameInstant(ZoneId.of(toZone));
}
```

---

## 6. Default and Static Methods in Interfaces

### Default Methods

```java
public interface Collection<E> {
    // Existing abstract method
    Iterator<E> iterator();

    // Default method - provides implementation, can be overridden
    default void forEach(Consumer<? super E> action) {
        for (E e : this) {
            action.accept(e);
        }
    }

    // Default method with logic
    default boolean removeIf(Predicate<? super E> filter) {
        boolean removed = false;
        Iterator<E> iter = iterator();
        while (iter.hasNext()) {
            if (filter.test(iter.next())) {
                iter.remove();
                removed = true;
            }
        }
        return removed;
    }
}

// Custom interface with default methods
public interface Validator<T> {
    boolean validate(T target);

    default Validator<T> and(Validator<T> other) {
        return target -> this.validate(target) && other.validate(target);
    }

    default Validator<T> or(Validator<T> other) {
        return target -> this.validate(target) || other.validate(target);
    }

    default Validator<T> negate() {
        return target -> !this.validate(target);
    }
}

// Usage
Validator<String> notEmpty = s -> !s.isEmpty();
Validator<String> notTooLong = s -> s.length() < 100;
Validator<String> combined = notEmpty.and(notTooLong);
```

### Static Methods in Interfaces

```java
public interface Comparator<T> {
    int compare(T o1, T o2);

    // Static factory methods
    static <T, U extends Comparable<? super U>> Comparator<T> comparing(
            Function<? super T, ? extends U> keyExtractor) {
        return (o1, o2) -> keyExtractor.apply(o1).compareTo(keyExtractor.apply(o2));
    }

    static <T> Comparator<T> naturalOrder() {
        return (Comparator<T>) Comparator.naturalOrder();
    }
}

// Custom interface with static methods
public interface StringUtils {
    static boolean isNullOrEmpty(String s) {
        return s == null || s.isEmpty();
    }

    static String repeat(String s, int times) {
        return s.repeat(times);  // Java 11
    }
}
// Called as: StringUtils.isNullOrEmpty(myString)
```

### Diamond Problem Resolution

```java
interface A {
    default void hello() { System.out.println("A"); }
}

interface B {
    default void hello() { System.out.println("B"); }
}

// Must override to resolve ambiguity
class C implements A, B {
    @Override
    public void hello() {
        A.super.hello();  // explicitly choose A's implementation
        // or B.super.hello();
        // or provide completely new implementation
    }
}

// Rules:
// 1. Class wins over interface (class method overrides interface default)
// 2. Sub-interface wins over super-interface (more specific wins)
// 3. If ambiguous, class MUST override (compile error otherwise)
```

### Interface Evolution Pattern

```java
// Version 1
public interface PaymentProcessor {
    void process(Payment payment);
}

// Version 2 - add method without breaking existing implementations
public interface PaymentProcessor {
    void process(Payment payment);

    // New default method - existing implementations still compile
    default void processAsync(Payment payment) {
        CompletableFuture.runAsync(() -> process(payment));
    }

    // Static utility
    static PaymentProcessor noOp() {
        return payment -> {};  // no-op implementation
    }
}
```

### Private Methods in Interfaces (Java 9)

```java
public interface Logger {
    default void logInfo(String message) {
        log("INFO", message);
    }

    default void logError(String message) {
        log("ERROR", message);
    }

    // Private method to share logic between default methods
    private void log(String level, String message) {
        System.out.println("[" + level + "] " + LocalDateTime.now() + ": " + message);
    }

    // Private static method
    private static String formatTimestamp() {
        return LocalDateTime.now().format(DateTimeFormatter.ISO_LOCAL_DATE_TIME);
    }
}
```

---

## 7. var - Local Variable Type Inference (Java 10+)

### Basic Usage

```java
// var infers type from right-hand side
var list = new ArrayList<String>();        // ArrayList<String>
var map = new HashMap<String, Integer>();  // HashMap<String, Integer>
var stream = list.stream();               // Stream<String>
var name = "hello";                       // String
var count = 42;                           // int (not Integer)
var pi = 3.14;                            // double (not Double)

// With diamond operator
var list2 = new ArrayList<>();  // ArrayList<Object> - diamond infers Object!
var list3 = new ArrayList<String>();  // Correct - specify type with diamond

// In for loops
for (var entry : map.entrySet()) {  // Map.Entry<String, Integer>
    var key = entry.getKey();       // String
    var value = entry.getValue();   // Integer
}

for (var i = 0; i < 10; i++) {  // int
    // ...
}

// With try-with-resources
try (var reader = new BufferedReader(new FileReader("file.txt"))) {
    var line = reader.readLine();
}
```

### Where var CANNOT Be Used

```java
// Cannot use for: method parameters
public void method(var param) { }  // COMPILE ERROR

// Cannot use for: method return types
public var getResult() { }  // COMPILE ERROR

// Cannot use for: fields (instance or static)
class MyClass {
    var name = "hello";  // COMPILE ERROR
}

// Cannot use without initializer
var x;  // COMPILE ERROR
x = 5;

// Cannot use with null (no type to infer)
var nothing = null;  // COMPILE ERROR

// Cannot use with lambda expressions (no target type)
var func = (String s) -> s.length();  // COMPILE ERROR
// Works with cast: var func = (Function<String, Integer>) s -> s.length();

// Cannot use with array initializer without new
var arr = {1, 2, 3};  // COMPILE ERROR
var arr = new int[]{1, 2, 3};  // OK

// Cannot use with method references (no target type)
var printer = System.out::println;  // COMPILE ERROR
```

### Best Practices

```java
// GOOD: Complex generic types - var improves readability
var groupedByDept = employees.stream()
    .collect(Collectors.groupingBy(Employee::getDepartment));
// Instead of: Map<String, List<Employee>> groupedByDept = ...

var entries = map.entrySet().iterator();
// Instead of: Iterator<Map.Entry<String, List<Integer>>> entries = ...

// GOOD: Obvious type from constructor/method name
var connection = DriverManager.getConnection(url);
var reader = new BufferedReader(new InputStreamReader(stream));
var employee = employeeRepository.findById(id);

// BAD: Obscures the type when not obvious
var result = process(data);  // What type is result?
var x = calculate();         // Unhelpful

// BAD: Numeric literals can be surprising
var num = 1;    // int
var num2 = 1L;  // long
var num3 = 1.0; // double
var num4 = 1.0f; // float

// var in lambda parameters (Java 11) - for annotations
list.stream()
    .map((@NonNull var item) -> item.toString())
    .collect(toList());
```

---

## 8. Practical LLD Examples

### Example 1: Filtering, Sorting, and Grouping - Employee Management

```java
public class EmployeeService {
    private final List<Employee> employees;

    public record Employee(
        Long id, String name, String department,
        double salary, int experience, List<String> skills,
        LocalDate joiningDate, Optional<Long> managerId
    ) {}

    // Find top N paid employees per department
    public Map<String, List<Employee>> topNByDepartment(int n) {
        return employees.stream()
            .collect(Collectors.groupingBy(
                Employee::department,
                Collectors.collectingAndThen(
                    Collectors.toList(),
                    list -> list.stream()
                        .sorted(Comparator.comparingDouble(Employee::salary).reversed())
                        .limit(n)
                        .toList()
                )
            ));
    }

    // Find employees who share skills with a given employee
    public List<Employee> findSimilar(Long employeeId) {
        Set<String> targetSkills = findById(employeeId)
            .map(Employee::skills)
            .map(HashSet::new)
            .orElse(new HashSet<>());

        return employees.stream()
            .filter(e -> !e.id().equals(employeeId))
            .filter(e -> e.skills().stream().anyMatch(targetSkills::contains))
            .sorted(Comparator.comparingLong((Employee e) ->
                e.skills().stream().filter(targetSkills::contains).count()
            ).reversed())
            .toList();
    }

    // Department hierarchy report
    public Map<String, Map<String, DoubleSummaryStatistics>> hierarchyReport() {
        return employees.stream()
            .collect(Collectors.groupingBy(
                Employee::department,
                Collectors.groupingBy(
                    e -> e.experience() > 10 ? "Senior" :
                         e.experience() > 5 ? "Mid" : "Junior",
                    Collectors.summarizingDouble(Employee::salary)
                )
            ));
    }

    // Salary percentile
    public OptionalDouble salaryPercentile(double percentile) {
        List<Double> sorted = employees.stream()
            .map(Employee::salary)
            .sorted()
            .toList();

        if (sorted.isEmpty()) return OptionalDouble.empty();
        int index = (int) Math.ceil(percentile / 100.0 * sorted.size()) - 1;
        return OptionalDouble.of(sorted.get(Math.max(0, index)));
    }

    // Org chart - find reporting chain
    public List<Employee> getReportingChain(Long employeeId) {
        List<Employee> chain = new ArrayList<>();
        Optional<Employee> current = findById(employeeId);

        while (current.isPresent()) {
            chain.add(current.get());
            current = current.get().managerId().flatMap(this::findById);
        }
        return chain;
    }

    private Optional<Employee> findById(Long id) {
        return employees.stream()
            .filter(e -> e.id().equals(id))
            .findFirst();
    }
}
```

### Example 2: Building Fluent APIs with Lambdas

```java
// Query Builder with lambda-based configuration
public class QueryBuilder<T> {
    private final List<Predicate<T>> filters = new ArrayList<>();
    private Comparator<T> sorter;
    private int offset = 0;
    private int limit = Integer.MAX_VALUE;
    private Function<T, ?> groupBy;

    public static <T> QueryBuilder<T> from(Class<T> type) {
        return new QueryBuilder<>();
    }

    public QueryBuilder<T> where(Predicate<T> condition) {
        filters.add(condition);
        return this;
    }

    public QueryBuilder<T> orderBy(Comparator<T> comparator) {
        this.sorter = comparator;
        return this;
    }

    public <U extends Comparable<U>> QueryBuilder<T> orderBy(
            Function<T, U> keyExtractor, boolean ascending) {
        Comparator<T> comp = Comparator.comparing(keyExtractor);
        this.sorter = ascending ? comp : comp.reversed();
        return this;
    }

    public QueryBuilder<T> skip(int offset) {
        this.offset = offset;
        return this;
    }

    public QueryBuilder<T> take(int limit) {
        this.limit = limit;
        return this;
    }

    public List<T> execute(List<T> source) {
        Stream<T> stream = source.stream();

        // Apply all filters
        Predicate<T> combined = filters.stream()
            .reduce(Predicate::and)
            .orElse(t -> true);
        stream = stream.filter(combined);

        // Apply sorting
        if (sorter != null) {
            stream = stream.sorted(sorter);
        }

        // Apply pagination
        return stream.skip(offset).limit(limit).toList();
    }
}

// Usage
List<Employee> results = QueryBuilder.from(Employee.class)
    .where(e -> e.department().equals("Engineering"))
    .where(e -> e.salary() > 80000)
    .orderBy(Employee::salary, false)
    .skip(0)
    .take(10)
    .execute(employees);
```

```java
// Event System with Functional Handlers
public class EventBus<E> {
    private final Map<Class<?>, List<Consumer<?>>> handlers = new ConcurrentHashMap<>();

    @SuppressWarnings("unchecked")
    public <T extends E> EventBus<E> on(Class<T> eventType, Consumer<T> handler) {
        handlers.computeIfAbsent(eventType, k -> new CopyOnWriteArrayList<>())
            .add(handler);
        return this;
    }

    @SuppressWarnings("unchecked")
    public <T extends E> void emit(T event) {
        Optional.ofNullable(handlers.get(event.getClass()))
            .ifPresent(list -> list.forEach(h -> ((Consumer<T>) h).accept(event)));
    }

    // Typed subscription with filter
    public <T extends E> EventBus<E> on(Class<T> eventType,
                                         Predicate<T> filter,
                                         Consumer<T> handler) {
        return on(eventType, event -> {
            if (filter.test(event)) handler.accept(event);
        });
    }
}

// Usage
EventBus<DomainEvent> bus = new EventBus<>();
bus.on(OrderCreated.class, event -> sendEmail(event.getCustomerEmail()))
   .on(OrderCreated.class, event -> updateInventory(event.getItems()))
   .on(PaymentFailed.class,
       event -> event.getAttempts() > 3,
       event -> alertOps(event));
```

```java
// Pipeline/Chain Pattern
public class Pipeline<I, O> {
    private final Function<I, O> function;

    private Pipeline(Function<I, O> function) {
        this.function = function;
    }

    public static <T> Pipeline<T, T> of(UnaryOperator<T> initial) {
        return new Pipeline<>(initial);
    }

    public static <I, O> Pipeline<I, O> of(Function<I, O> initial) {
        return new Pipeline<>(initial);
    }

    public <R> Pipeline<I, R> pipe(Function<O, R> next) {
        return new Pipeline<>(function.andThen(next));
    }

    public <R> Pipeline<I, R> pipeIf(Predicate<O> condition,
                                      Function<O, R> ifTrue,
                                      Function<O, R> ifFalse) {
        return new Pipeline<>(input -> {
            O result = function.apply(input);
            return condition.test(result) ? ifTrue.apply(result) : ifFalse.apply(result);
        });
    }

    public O execute(I input) {
        return function.apply(input);
    }
}

// Usage
Pipeline<String, String> textProcessor = Pipeline.of((String s) -> s)
    .pipe(String::trim)
    .pipe(String::toLowerCase)
    .pipe(s -> s.replaceAll("[^a-z0-9\\s]", ""))
    .pipe(s -> s.replaceAll("\\s+", "-"));

String slug = textProcessor.execute("  Hello, World! 123  ");  // "hello-world-123"
```

### Example 3: Optional for Null Safety in Service Layers

```java
// Repository
public interface UserRepository {
    Optional<User> findById(Long id);
    Optional<User> findByEmail(String email);
}

public interface OrderRepository {
    Optional<Order> findById(String orderId);
    List<Order> findByUserId(Long userId);
}

// Service with proper Optional usage
public class OrderService {
    private final UserRepository userRepo;
    private final OrderRepository orderRepo;
    private final NotificationService notificationService;

    // Return Optional when result may not exist
    public Optional<OrderDTO> getOrderDetails(String orderId) {
        return orderRepo.findById(orderId)
            .filter(order -> order.getStatus() != Status.DELETED)
            .map(order -> {
                var user = userRepo.findById(order.getUserId())
                    .orElseThrow(() -> new DataIntegrityException(
                        "Order %s references non-existent user %d"
                            .formatted(orderId, order.getUserId())));
                return toDTO(order, user);
            });
    }

    // orElseThrow when absence is exceptional
    public OrderDTO placeOrder(Long userId, CreateOrderRequest request) {
        User user = userRepo.findById(userId)
            .orElseThrow(() -> new UserNotFoundException(userId));

        Order order = createOrder(user, request);

        // ifPresent for optional side effects
        user.getEmail().ifPresent(email ->
            notificationService.sendOrderConfirmation(email, order));

        return toDTO(order, user);
    }

    // Cascading lookups with or()
    public Optional<User> resolveUser(String identifier) {
        return userRepo.findByEmail(identifier)
            .or(() -> {
                try {
                    return userRepo.findById(Long.parseLong(identifier));
                } catch (NumberFormatException e) {
                    return Optional.empty();
                }
            });
    }

    // flatMap for chained Optional navigation
    public Optional<String> getOrderShippingCity(String orderId) {
        return orderRepo.findById(orderId)
            .flatMap(Order::getShippingAddress)
            .flatMap(Address::getCity);
    }

    // Collecting non-empty Optionals from a stream
    public List<String> getActiveUserEmails(List<Long> userIds) {
        return userIds.stream()
            .map(userRepo::findById)
            .flatMap(Optional::stream)  // only present values
            .filter(User::isActive)
            .map(User::getEmail)
            .flatMap(Optional::stream)  // users may not have emails
            .toList();
    }

    // Pattern: Compute-if-absent with Optional
    public UserProfile getOrCreateProfile(Long userId) {
        return profileRepo.findByUserId(userId)
            .orElseGet(() -> {
                User user = userRepo.findById(userId)
                    .orElseThrow(() -> new UserNotFoundException(userId));
                return profileRepo.save(new UserProfile(user));
            });
    }
}
```

### Example 4: Complete Notification System Using Java 8+ Features

```java
// Demonstrates: lambdas, functional interfaces, streams, Optional, default methods
public class NotificationSystem {

    // Custom functional interface
    @FunctionalInterface
    public interface NotificationFilter {
        boolean shouldSend(Notification notification, UserPreferences prefs);

        default NotificationFilter and(NotificationFilter other) {
            return (n, p) -> this.shouldSend(n, p) && other.shouldSend(n, p);
        }

        default NotificationFilter or(NotificationFilter other) {
            return (n, p) -> this.shouldSend(n, p) || other.shouldSend(n, p);
        }

        static NotificationFilter always() { return (n, p) -> true; }
        static NotificationFilter never() { return (n, p) -> false; }
    }

    // Interface with default methods
    public interface NotificationChannel {
        void send(Notification notification, User user);
        boolean supports(NotificationType type);

        default void sendBatch(List<Notification> notifications, User user) {
            notifications.stream()
                .filter(n -> supports(n.getType()))
                .forEach(n -> send(n, user));
        }
    }

    // Service using streams and Optional
    public class NotificationService {
        private final List<NotificationChannel> channels;
        private final Map<NotificationType, NotificationFilter> filters;
        private final Function<Notification, Notification> enricher;

        public NotificationService(
                List<NotificationChannel> channels,
                Map<NotificationType, NotificationFilter> filters,
                Function<Notification, Notification> enricher) {
            this.channels = channels;
            this.filters = filters;
            this.enricher = enricher;
        }

        public void notify(User user, Notification notification) {
            var prefs = user.getPreferences().orElse(UserPreferences.defaults());

            Optional.of(notification)
                .map(enricher)
                .filter(n -> getFilter(n.getType()).shouldSend(n, prefs))
                .ifPresent(n -> deliverToChannels(n, user, prefs));
        }

        public Map<NotificationType, Long> notifyBatch(
                List<User> users, Notification notification) {
            return users.parallelStream()
                .filter(User::isActive)
                .filter(u -> u.getPreferences()
                    .map(p -> !p.isDoNotDisturb())
                    .orElse(true))
                .peek(u -> notify(u, notification))
                .collect(Collectors.groupingBy(
                    u -> notification.getType(),
                    Collectors.counting()
                ));
        }

        private void deliverToChannels(Notification n, User user, UserPreferences prefs) {
            channels.stream()
                .filter(ch -> ch.supports(n.getType()))
                .filter(ch -> prefs.getEnabledChannels().contains(ch.getClass().getSimpleName()))
                .forEach(ch -> ch.send(n, user));
        }

        private NotificationFilter getFilter(NotificationType type) {
            return Optional.ofNullable(filters.get(type))
                .orElse(NotificationFilter.always());
        }
    }

    // Builder using lambdas
    public static class NotificationServiceBuilder {
        private final List<NotificationChannel> channels = new ArrayList<>();
        private final Map<NotificationType, NotificationFilter> filters = new EnumMap<>(NotificationType.class);
        private Function<Notification, Notification> enricher = Function.identity();

        public NotificationServiceBuilder channel(NotificationChannel channel) {
            channels.add(channel);
            return this;
        }

        public NotificationServiceBuilder filter(NotificationType type, NotificationFilter filter) {
            filters.merge(type, filter, NotificationFilter::and);
            return this;
        }

        public NotificationServiceBuilder enrich(UnaryOperator<Notification> step) {
            this.enricher = this.enricher.andThen(step);
            return this;
        }

        public NotificationService build() {
            return new NotificationService(
                List.copyOf(channels),
                Map.copyOf(filters),
                enricher
            );
        }
    }
}

// Construction
NotificationService service = new NotificationSystem.NotificationServiceBuilder()
    .channel(new EmailChannel())
    .channel(new PushChannel())
    .filter(NotificationType.MARKETING,
        (n, prefs) -> prefs.isMarketingOptedIn())
    .filter(NotificationType.MARKETING,
        (n, prefs) -> !prefs.isDoNotDisturb())
    .enrich(n -> n.withTimestamp(Instant.now()))
    .enrich(n -> n.withTraceId(UUID.randomUUID().toString()))
    .build();
```

### Example 5: Stream-Based Rule Engine

```java
public class RuleEngine<T> {
    private final List<Rule<T>> rules;

    @FunctionalInterface
    public interface Rule<T> {
        Optional<String> evaluate(T target);

        default Rule<T> when(Predicate<T> condition) {
            return target -> condition.test(target) ? evaluate(target) : Optional.empty();
        }
    }

    public record ValidationResult(boolean valid, List<String> errors) {
        public static ValidationResult success() { return new ValidationResult(true, List.of()); }
        public static ValidationResult failure(List<String> errors) {
            return new ValidationResult(false, errors);
        }
    }

    public ValidationResult validate(T target) {
        List<String> errors = rules.stream()
            .map(rule -> rule.evaluate(target))
            .flatMap(Optional::stream)
            .toList();
        return errors.isEmpty()
            ? ValidationResult.success()
            : ValidationResult.failure(errors);
    }

    // Builder
    public static <T> Builder<T> builder() { return new Builder<>(); }

    public static class Builder<T> {
        private final List<Rule<T>> rules = new ArrayList<>();

        public Builder<T> addRule(Predicate<T> condition, String errorMessage) {
            rules.add(target -> condition.test(target)
                ? Optional.empty()
                : Optional.of(errorMessage));
            return this;
        }

        public Builder<T> addRule(Predicate<T> condition,
                                   Function<T, String> errorMessageFn) {
            rules.add(target -> condition.test(target)
                ? Optional.empty()
                : Optional.of(errorMessageFn.apply(target)));
            return this;
        }

        public RuleEngine<T> build() {
            return new RuleEngine<>(List.copyOf(rules));
        }
    }
}

// Usage
RuleEngine<Employee> employeeValidator = RuleEngine.<Employee>builder()
    .addRule(e -> e.name() != null && !e.name().isBlank(), "Name is required")
    .addRule(e -> e.salary() > 0, "Salary must be positive")
    .addRule(e -> e.salary() <= 500000,
        e -> "Salary %.0f exceeds maximum 500000".formatted(e.salary()))
    .addRule(e -> e.experience() >= 0, "Experience cannot be negative")
    .addRule(
        e -> e.department() != null,
        "Department is required"
    )
    .build();

ValidationResult result = employeeValidator.validate(newEmployee);
if (!result.valid()) {
    throw new ValidationException(result.errors());
}
```

---

## Quick Reference: Common Patterns

| Pattern | Code |
|---------|------|
| Filter + Collect | `list.stream().filter(pred).toList()` |
| Map + Collect | `list.stream().map(fn).toList()` |
| FlatMap nested | `nested.stream().flatMap(Collection::stream).toList()` |
| Group by | `stream.collect(groupingBy(classifier))` |
| Group + Count | `stream.collect(groupingBy(classifier, counting()))` |
| Partition | `stream.collect(partitioningBy(pred))` |
| Max/Min | `stream.max(Comparator.comparing(fn))` |
| Sum | `stream.mapToInt(fn).sum()` |
| Join strings | `stream.map(fn).collect(joining(", "))` |
| Distinct sorted | `stream.distinct().sorted().toList()` |
| First match | `stream.filter(pred).findFirst()` |
| Any/All/None | `stream.anyMatch(pred)` |
| To map | `stream.collect(toMap(keyFn, valFn))` |
| Reduce | `stream.reduce(identity, accumulator)` |
| Peek debug | `stream.peek(System.out::println).collect(...)` |
| Paginate | `stream.skip(offset).limit(pageSize).toList()` |
| Frequency map | `stream.collect(groupingBy(identity(), counting()))` |
| Optional chain | `opt.flatMap(fn).map(fn).orElse(default)` |
| Null-safe get | `Optional.ofNullable(x).map(fn).orElse(default)` |

---

## Version Summary

| Feature | Java Version |
|---------|-------------|
| Lambdas, Streams, Optional, Functional Interfaces | 8 |
| Default/Static interface methods | 8 |
| java.time API | 8 |
| Private interface methods | 9 |
| takeWhile, dropWhile, ofNullable, Stream.iterate with predicate | 9 |
| ifPresentOrElse, Optional.or, Optional.stream | 9 |
| var (local variables) | 10 |
| toUnmodifiableList/Set/Map | 10 |
| var in lambdas, String::isBlank, Optional.isEmpty | 11 |
| Collectors.teeing | 12 |
| switch expressions | 14 |
| Records, Pattern matching instanceof | 16 |
| Stream.toList() | 16 |
| Sealed classes | 17 |
| Pattern matching for switch | 21 |
