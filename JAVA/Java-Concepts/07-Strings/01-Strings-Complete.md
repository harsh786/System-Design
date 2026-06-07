# Complete Guide to Strings in Java

## 1. String Internals

### 1.1 Immutability

Strings in Java are **immutable** - once created, their value cannot be changed.

```java
String s = "Hello";
s.concat(" World"); // Creates NEW string, doesn't modify s
System.out.println(s); // Still "Hello"

s = s.concat(" World"); // s now POINTS to new object
System.out.println(s); // "Hello World"
```

**Why are Strings immutable?**

| Reason | Explanation |
|--------|-------------|
| **Security** | Strings used in network connections, file paths, DB URLs. If mutable, attacker could change after validation |
| **Thread Safety** | Immutable objects are inherently thread-safe. No synchronization needed |
| **HashCode Caching** | String caches its hashCode. Used heavily in HashMap keys. If mutable, hash would change |
| **String Pool** | JVM can reuse String literals because they can't be modified |
| **Class Loading** | Class names are Strings. If mutable, could load wrong class |

```java
// Security Example
public void connect(String url) {
    // If String were mutable, url could change between validation and use
    if (isValid(url)) {
        // Another thread could modify url HERE if it were mutable
        openConnection(url); // Could connect to malicious server
    }
}

// HashCode Caching
public final class String {
    private int hash; // Default 0 - cached after first calculation
    
    public int hashCode() {
        int h = hash;
        if (h == 0 && value.length > 0) {
            // Calculate hash only ONCE
            for (int i = 0; i < value.length; i++) {
                h = 31 * h + value[i];
            }
            hash = h; // Cache it
        }
        return h;
    }
}
```

### 1.2 String Pool (String Constant Pool)

The **String Pool** is a special memory area in the **Heap** (moved from PermGen in Java 7+) that stores unique string literals.

```java
// Both point to SAME object in String Pool
String s1 = "Hello";
String s2 = "Hello";
System.out.println(s1 == s2); // true (same reference)

// Creates object in HEAP (not pool)
String s3 = new String("Hello");
System.out.println(s1 == s3); // false (different references)

// intern() moves string to pool / returns pool reference
String s4 = s3.intern();
System.out.println(s1 == s4); // true (s4 points to pool)
```

**Memory Diagram:**
```
String Pool (inside Heap):
┌──────────────────────────────┐
│  "Hello" ←── s1, s2, s4     │
│  "World"                      │
│  "Java"                       │
└──────────────────────────────┘

Heap (outside pool):
┌──────────────────────────────┐
│  String("Hello") ←── s3      │  (separate object)
└──────────────────────────────┘

Stack:
┌──────────────────────────────┐
│  s1 → [ref to pool "Hello"]  │
│  s2 → [ref to pool "Hello"]  │
│  s3 → [ref to heap object]   │
│  s4 → [ref to pool "Hello"]  │
└──────────────────────────────┘
```

### 1.3 How Many Objects Created?

```java
// Q1: How many objects?
String s = "Hello";
// Answer: 1 (in String Pool, if not already there) or 0 (if already in pool)

// Q2: How many objects?
String s = new String("Hello");
// Answer: Up to 2
//   1. "Hello" literal in String Pool (if not already there)
//   2. new String object in Heap

// Q3: How many objects?
String s = new String("Hello") + new String("World");
// Answer: Up to 5
//   1. "Hello" in pool
//   2. new String("Hello") in heap
//   3. "World" in pool
//   4. new String("World") in heap
//   5. "HelloWorld" in heap (result of concatenation via StringBuilder)
//   NOTE: "HelloWorld" is NOT automatically in the pool

// Q4:
String s1 = "Hello";        // Pool: "Hello"
String s2 = "Hel" + "lo";  // Compile-time constant → Pool: "Hello" (same!)
System.out.println(s1 == s2); // true (compiler concatenates at compile time)

// Q5:
String s1 = "Hello";
String part = "lo";
String s2 = "Hel" + part;  // Runtime concatenation → Heap object
System.out.println(s1 == s2); // false

// Q6:
final String part = "lo";   // final makes it compile-time constant
String s2 = "Hel" + part;   // Resolved at compile time!
String s1 = "Hello";
System.out.println(s1 == s2); // true
```

### 1.4 == vs equals()

```java
// == compares REFERENCES (memory addresses)
// equals() compares VALUES (content)

String a = "Java";
String b = "Java";
String c = new String("Java");
String d = new String("Java");

System.out.println(a == b);        // true  (both point to pool)
System.out.println(a == c);        // false (pool vs heap)
System.out.println(c == d);        // false (different heap objects)
System.out.println(a.equals(b));   // true  (same content)
System.out.println(a.equals(c));   // true  (same content)
System.out.println(c.equals(d));   // true  (same content)

// TRICKY: null handling
String x = null;
// x.equals("test");  // NullPointerException!
"test".equals(x);     // false (safe - no NPE)
Objects.equals(x, "test"); // false (null-safe utility)
```

### 1.5 String Internal Implementation

```java
// Java 8 and earlier: char[] array
public final class String {
    private final char[] value; // Each char = 2 bytes (UTF-16)
}

// Java 9+: Compact Strings - byte[] array
public final class String {
    private final byte[] value;  // Can be 1 byte per char (Latin-1) 
    private final byte coder;    // 0 = Latin-1, 1 = UTF-16
    // Saves ~40% memory for Latin-1 strings
}
```

---

## 2. String Methods (Complete Reference)

### 2.1 Basic Methods

```java
String s = "Hello World";

// Length
s.length();           // 11

// Character access
s.charAt(0);          // 'H'
s.charAt(4);          // 'o'
// s.charAt(11);      // StringIndexOutOfBoundsException

// Check empty/blank
"".isEmpty();         // true
" ".isEmpty();        // false
" ".isBlank();        // true  (Java 11 - checks whitespace)
"  \t\n".isBlank();  // true
"Hi".isBlank();      // false
```

### 2.2 Searching

```java
String s = "Hello World Hello";

// indexOf - first occurrence
s.indexOf('o');           // 4
s.indexOf('o', 5);       // 7 (search from index 5)
s.indexOf("World");      // 6
s.indexOf("xyz");        // -1 (not found)

// lastIndexOf - last occurrence
s.lastIndexOf('o');       // 13
s.lastIndexOf("Hello");  // 12

// contains
s.contains("World");     // true
s.contains("world");     // false (case-sensitive)

// startsWith / endsWith
s.startsWith("Hello");   // true
s.startsWith("World", 6); // true (starts at index 6)
s.endsWith("Hello");     // true
```

### 2.3 Substring & Subparts

```java
String s = "Hello World";

// substring(beginIndex) - from index to end
s.substring(6);       // "World"

// substring(beginIndex, endIndex) - [begin, end)
s.substring(0, 5);    // "Hello"
s.substring(6, 11);   // "World"

// subSequence (returns CharSequence)
s.subSequence(0, 5);  // "Hello"

// toCharArray
char[] chars = s.toCharArray(); // ['H','e','l','l','o',' ','W','o','r','l','d']

// split
String csv = "apple,banana,cherry";
String[] parts = csv.split(",");     // ["apple", "banana", "cherry"]
String[] limited = csv.split(",", 2); // ["apple", "banana,cherry"]

// Split with regex
"hello   world".split("\\s+");      // ["hello", "world"]
"a.b.c".split("\\.");               // ["a", "b", "c"]

// join (Java 8)
String joined = String.join(", ", "a", "b", "c"); // "a, b, c"
String joined2 = String.join("-", parts);          // "apple-banana-cherry"
```

### 2.4 Comparison

```java
String s1 = "Hello";
String s2 = "hello";

// equals / equalsIgnoreCase
s1.equals(s2);            // false
s1.equalsIgnoreCase(s2);  // true

// compareTo (lexicographic) - returns int
"apple".compareTo("banana");   // negative (a < b)
"banana".compareTo("apple");   // positive (b > a)
"apple".compareTo("apple");    // 0 (equal)
"Apple".compareTo("apple");    // negative (uppercase < lowercase)

// compareToIgnoreCase
"Apple".compareToIgnoreCase("apple"); // 0

// contentEquals (compare with CharSequence/StringBuffer)
"Hello".contentEquals(new StringBuilder("Hello")); // true
```

### 2.5 Transformation

```java
String s = "  Hello World  ";

// Trimming
s.trim();           // "Hello World" (removes <= ' ' chars)
s.strip();          // "Hello World" (Java 11 - Unicode aware)
s.stripLeading();   // "Hello World  " (Java 11)
s.stripTrailing();  // "  Hello World" (Java 11)

// trim() vs strip():
// trim() removes characters with codepoint <= 32 (space)
// strip() uses Character.isWhitespace() - handles Unicode whitespace
String unicode = "\u2005Hello\u2005"; // Unicode thin space
unicode.trim();   // "\u2005Hello\u2005" (doesn't remove unicode whitespace!)
unicode.strip();  // "Hello" (removes it!)

// Case conversion
"Hello".toUpperCase();    // "HELLO"
"Hello".toLowerCase();    // "hello"
// Locale-specific
"Hello".toUpperCase(Locale.TURKISH); // "HELLO" with Turkish rules

// Replace
"Hello World".replace('l', 'L');           // "HeLLo WorLd"
"Hello World".replace("World", "Java");    // "Hello Java"

// Replace with regex
"Hello 123 World 456".replaceAll("\\d+", "#");  // "Hello # World #"
"Hello 123 World 456".replaceFirst("\\d+", "#"); // "Hello # World 456"

// Repeat (Java 11)
"Ha".repeat(3);        // "HaHaHa"
"-".repeat(20);        // "--------------------"

// indent (Java 12)
"Hello\nWorld".indent(4);  // "    Hello\n    World\n"
```

### 2.6 Conversion & Formatting

```java
// valueOf - convert anything to String
String.valueOf(123);        // "123"
String.valueOf(3.14);       // "3.14"
String.valueOf(true);       // "true"
String.valueOf('c');        // "c"
String.valueOf(new char[]{'H','i'}); // "Hi"
String.valueOf((Object)null);        // "null"

// format
String.format("Hello %s, you are %d years old", "John", 25);
// "Hello John, you are 25 years old"

String.format("%10s", "Hi");     // "        Hi" (right-aligned, width 10)
String.format("%-10s", "Hi");    // "Hi        " (left-aligned)
String.format("%.2f", 3.14159);  // "3.14"
String.format("%05d", 42);       // "00042" (zero-padded)
String.format("%,d", 1000000);   // "1,000,000"
String.format("%x", 255);        // "ff" (hex)
String.format("%o", 8);          // "10" (octal)

// formatted (Java 15) - instance method
"Hello %s".formatted("World");   // "Hello World"

// getBytes
byte[] bytes = "Hello".getBytes();                    // Platform default encoding
byte[] utf8 = "Hello".getBytes(StandardCharsets.UTF_8);
byte[] utf16 = "Hello".getBytes(StandardCharsets.UTF_16);

// Constructing from bytes
new String(utf8, StandardCharsets.UTF_8);  // "Hello"
```

### 2.7 Streams (Java 8+)

```java
String s = "Hello World";

// chars() - IntStream of char values
s.chars()
    .filter(c -> c != ' ')
    .forEach(c -> System.out.print((char) c)); // "HelloWorld"

// Count vowels
long vowelCount = s.chars()
    .filter(c -> "aeiouAEIOU".indexOf(c) != -1)
    .count(); // 3

// codePoints() - IntStream of Unicode code points
"Hello 🌍".codePoints()
    .forEach(cp -> System.out.println(Character.getName(cp)));

// Convert to stream of characters
List<Character> charList = s.chars()
    .mapToObj(c -> (char) c)
    .collect(Collectors.toList());

// lines() (Java 11) - stream of lines
"Line1\nLine2\nLine3".lines()
    .filter(line -> line.contains("2"))
    .forEach(System.out::println); // "Line2"
```

### 2.8 Matching & Regex

```java
String s = "Hello123World";

// matches - entire string must match regex
s.matches("[a-zA-Z0-9]+");     // true
s.matches("[a-zA-Z]+");         // false (has digits)
"12345".matches("\\d+");       // true
"hello@email.com".matches("[\\w.]+@[\\w.]+"); // true

// regionMatches
"Hello World".regionMatches(6, "World Cup", 0, 5); // true
// Case-insensitive version
"Hello World".regionMatches(true, 0, "HELLO", 0, 5); // true
```

### 2.9 Complete Method Quick Reference Table

| Method | Description | Since |
|--------|-------------|-------|
| `charAt(int)` | Char at index | 1.0 |
| `length()` | Number of chars | 1.0 |
| `isEmpty()` | True if length == 0 | 1.6 |
| `isBlank()` | True if empty or only whitespace | 11 |
| `substring(int)` | From index to end | 1.0 |
| `substring(int, int)` | From start (inclusive) to end (exclusive) | 1.0 |
| `indexOf(String)` | First occurrence index | 1.0 |
| `lastIndexOf(String)` | Last occurrence index | 1.0 |
| `contains(CharSequence)` | Checks containment | 1.5 |
| `startsWith(String)` | Prefix check | 1.0 |
| `endsWith(String)` | Suffix check | 1.0 |
| `equals(Object)` | Content equality | 1.0 |
| `equalsIgnoreCase(String)` | Case-insensitive equality | 1.0 |
| `compareTo(String)` | Lexicographic comparison | 1.0 |
| `trim()` | Remove <= ' ' from both ends | 1.0 |
| `strip()` | Unicode-aware trim | 11 |
| `stripLeading()` | Remove leading whitespace | 11 |
| `stripTrailing()` | Remove trailing whitespace | 11 |
| `toUpperCase()` | Convert to uppercase | 1.0 |
| `toLowerCase()` | Convert to lowercase | 1.0 |
| `replace(char, char)` | Replace all chars | 1.0 |
| `replace(CharSequence, CharSequence)` | Replace all substrings | 1.5 |
| `replaceAll(String, String)` | Replace with regex | 1.4 |
| `replaceFirst(String, String)` | Replace first regex match | 1.4 |
| `split(String)` | Split by regex | 1.4 |
| `join(CharSequence, CharSequence...)` | Join strings with delimiter | 8 |
| `format(String, Object...)` | Printf-style formatting | 1.5 |
| `formatted(Object...)` | Instance format method | 15 |
| `chars()` | IntStream of chars | 9 |
| `codePoints()` | IntStream of code points | 9 |
| `lines()` | Stream of lines | 11 |
| `repeat(int)` | Repeat n times | 11 |
| `indent(int)` | Adjust indentation | 12 |
| `stripIndent()` | Remove incidental whitespace | 15 |
| `translateEscapes()` | Process escape sequences | 15 |
| `intern()` | Return pool reference | 1.0 |
| `toCharArray()` | Convert to char[] | 1.0 |
| `getBytes(Charset)` | Convert to byte[] | 1.6 |
| `valueOf(...)` | Convert to String (static) | 1.0 |
| `matches(String)` | Regex match entire string | 1.4 |
| `contentEquals(CharSequence)` | Compare with CharSequence | 1.5 |

---

## 3. StringBuilder

### 3.1 Why StringBuilder?

```java
// BAD: String concatenation in loop creates many objects
String result = "";
for (int i = 0; i < 10000; i++) {
    result += i; // Creates new String object EACH iteration!
}
// Creates ~10000 String objects + ~10000 StringBuilder objects (compiler)

// GOOD: StringBuilder
StringBuilder sb = new StringBuilder();
for (int i = 0; i < 10000; i++) {
    sb.append(i); // Modifies same object
}
String result = sb.toString();
```

### 3.2 Internal Mechanism

```java
// StringBuilder internally uses a char[] (or byte[] in Java 9+)
public final class StringBuilder {
    byte[] value;  // Internal buffer
    int count;     // Number of characters used
    
    // Default capacity: 16
    public StringBuilder() {
        value = new byte[16];
    }
    
    // Capacity = string length + 16
    public StringBuilder(String str) {
        value = new byte[str.length() + 16];
        append(str);
    }
    
    // Custom initial capacity
    public StringBuilder(int capacity) {
        value = new byte[capacity];
    }
}

// Growth mechanism when buffer is full:
// newCapacity = (oldCapacity + 1) * 2
// If still not enough: newCapacity = required length
```

### 3.3 All Methods

```java
StringBuilder sb = new StringBuilder("Hello");

// === APPEND (returns 'this' for chaining) ===
sb.append(" World");          // "Hello World"
sb.append(123);               // "Hello World123"
sb.append(true);              // "Hello World123true"
sb.append('!');               // "Hello World123true!"
sb.append(3.14);              // "Hello World123true!3.14"
sb.append(new char[]{'a','b'}); // Append char array

// Method chaining
sb = new StringBuilder();
sb.append("Hello").append(" ").append("World").append("!"); // "Hello World!"

// === INSERT ===
sb = new StringBuilder("Hello World");
sb.insert(5, " Beautiful");   // "Hello Beautiful World"
sb.insert(0, ">> ");          // ">> Hello Beautiful World"

// === DELETE ===
sb = new StringBuilder("Hello World");
sb.delete(5, 11);             // "Hello" (delete from index 5 to 10)
sb.deleteCharAt(4);           // "Hell" (delete char at index 4)

// === REPLACE ===
sb = new StringBuilder("Hello World");
sb.replace(6, 11, "Java");   // "Hello Java"

// === REVERSE ===
sb = new StringBuilder("Hello");
sb.reverse();                 // "olleH"

// === CHARACTER ACCESS ===
sb = new StringBuilder("Hello");
sb.charAt(0);                 // 'H'
sb.setCharAt(0, 'h');         // "hello"

// === LENGTH & CAPACITY ===
sb = new StringBuilder();     // Default capacity 16
sb.capacity();                // 16
sb.length();                  // 0
sb.append("Hello");
sb.length();                  // 5
sb.capacity();                // 16 (unchanged - buffer not full)

sb.ensureCapacity(100);       // Ensure at least 100
sb.trimToSize();              // Reduce capacity to match length

// === SUBSEQUENCE & SUBSTRING ===
sb = new StringBuilder("Hello World");
sb.substring(6);              // "World" (returns String)
sb.substring(0, 5);           // "Hello" (returns String)
sb.subSequence(0, 5);         // "Hello" (returns CharSequence)

// === INDEX SEARCH ===
sb = new StringBuilder("Hello World Hello");
sb.indexOf("Hello");          // 0
sb.indexOf("Hello", 1);      // 12 (search from index 1)
sb.lastIndexOf("Hello");     // 12
```

### 3.4 Capacity Growth Demonstration

```java
StringBuilder sb = new StringBuilder(); // capacity = 16

System.out.println("Initial capacity: " + sb.capacity()); // 16

sb.append("1234567890123456"); // Fills 16 chars exactly
System.out.println("Capacity: " + sb.capacity()); // 16

sb.append("7"); // Triggers growth: (16 + 1) * 2 = 34
System.out.println("Capacity: " + sb.capacity()); // 34

// If you know the approximate size, pre-allocate:
StringBuilder sb2 = new StringBuilder(1000); // Avoids multiple resizes
```

---

## 4. StringBuffer

### 4.1 StringBuffer vs StringBuilder

```java
// StringBuffer = synchronized (thread-safe) version of StringBuilder
// Same API, just synchronized methods

// StringBuffer - thread-safe but slower
StringBuffer buffer = new StringBuffer("Hello");
buffer.append(" World"); // synchronized method

// StringBuilder - NOT thread-safe but faster
StringBuilder builder = new StringBuilder("Hello");
builder.append(" World"); // not synchronized
```

| Feature | StringBuilder | StringBuffer |
|---------|--------------|--------------|
| Thread-safe | No | Yes (synchronized) |
| Performance | Faster | Slower (~15-20%) |
| Since | Java 1.5 | Java 1.0 |
| Use case | Single-threaded | Multi-threaded (rare) |

### 4.2 When to Use StringBuffer

```java
// Almost NEVER in modern Java. Use StringBuilder + external synchronization instead.

// Rare case: shared buffer between threads (usually better alternatives exist)
public class SharedLogger {
    private final StringBuffer buffer = new StringBuffer();
    
    // Multiple threads can call this safely
    public void log(String message) {
        buffer.append(Thread.currentThread().getName())
              .append(": ")
              .append(message)
              .append("\n");
    }
    
    public String getLogs() {
        return buffer.toString();
    }
}

// Better approach in modern Java:
// Use StringBuilder with explicit locks, or use concurrent data structures
```

---

## 5. String Concatenation Performance

### 5.1 Compiler Optimization

```java
// The + operator is compiled to StringBuilder (before Java 9)
// or invokedynamic StringConcatFactory (Java 9+)

// This:
String s = "Hello" + " " + "World";
// Compiles to:
String s = "Hello World"; // Compile-time constant folding!

// This:
String name = getName();
String s = "Hello " + name + "!";
// Java 9+: Uses invokedynamic (more efficient than StringBuilder)
// Pre-Java 9: Compiles to:
String s = new StringBuilder().append("Hello ").append(name).append("!").toString();
```

### 5.2 Performance Comparison

```java
// BENCHMARK: Concatenating 100,000 strings

// Method 1: + in loop (WORST - O(n^2))
String result = "";
for (int i = 0; i < 100000; i++) {
    result += i; // Creates new String each time!
}
// Time: ~6500ms (exponentially worse with size)
// Reason: Each += copies the ENTIRE existing string

// Method 2: StringBuilder (BEST for single thread)
StringBuilder sb = new StringBuilder();
for (int i = 0; i < 100000; i++) {
    sb.append(i);
}
String result = sb.toString();
// Time: ~5ms

// Method 3: StringBuilder with pre-allocated capacity (SLIGHTLY BETTER)
StringBuilder sb = new StringBuilder(600000); // Estimate size
for (int i = 0; i < 100000; i++) {
    sb.append(i);
}
String result = sb.toString();
// Time: ~4ms (avoids array resizing)

// Method 4: StringBuffer (thread-safe, slightly slower)
StringBuffer buf = new StringBuffer();
for (int i = 0; i < 100000; i++) {
    buf.append(i);
}
String result = buf.toString();
// Time: ~7ms (synchronization overhead)

// Method 5: String.join (good for joining collections)
List<String> list = Arrays.asList("a", "b", "c", "d");
String result = String.join(", ", list);
// Best for: joining known collections with delimiters

// Method 6: Collectors.joining (streams)
String result = IntStream.range(0, 100000)
    .mapToObj(Integer::toString)
    .collect(Collectors.joining());
// Time: ~15ms (stream overhead, but readable)
```

### 5.3 When to Use What

```java
// Simple concatenation (few strings, no loop): Use +
String greeting = "Hello, " + name + "! Welcome.";

// Concatenation in loop: Use StringBuilder
StringBuilder sb = new StringBuilder();
for (String item : items) {
    sb.append(item).append(", ");
}

// Joining with delimiter: Use String.join or Collectors.joining
String csv = String.join(",", list);
String piped = list.stream().collect(Collectors.joining(" | "));

// Multi-threaded (rare): Use StringBuffer or StringBuilder + locks
// Building complex output: Use StringBuilder with method chaining
```

---

## 6. Text Blocks (Java 13+, Standard in Java 15)

### 6.1 Basic Text Blocks

```java
// Old way - messy escaping
String json = "{\n" +
    "    \"name\": \"John\",\n" +
    "    \"age\": 30,\n" +
    "    \"city\": \"New York\"\n" +
    "}";

// Text Block - clean and readable
String json = """
        {
            "name": "John",
            "age": 30,
            "city": "New York"
        }
        """;

// HTML
String html = """
        <html>
            <body>
                <h1>Hello World</h1>
            </body>
        </html>
        """;

// SQL
String sql = """
        SELECT id, name, email
        FROM users
        WHERE active = true
        ORDER BY name
        """;
```

### 6.2 Indentation Management

```java
// The CLOSING """ determines the base indentation
// Everything to the right of closing """ is kept

// No indentation (closing """ at column 0 equivalent):
String s = """
Hello
World""";
// Result: "Hello\nWorld"

// 4-space indentation relative to closing """:
String s = """
        Hello
        World
    """;
// "    Hello\n    World\n" (4 spaces indent relative to closing """)

// stripIndent() removes common leading whitespace:
String s = """
        Hello
        World
        """;
// Result: "Hello\nWorld\n" (common indent stripped)

// Using \s to preserve trailing whitespace (it's stripped by default):
String s = """
        Hello   \s
        World   \s
        """;

// Using \ to prevent newline at end of line:
String s = """
        Hello \
        World""";
// Result: "Hello World" (single line!)
```

### 6.3 Text Block with Formatted Values

```java
String name = "John";
int age = 30;

// Using formatted()
String message = """
        Dear %s,
        You are %d years old.
        Welcome!
        """.formatted(name, age);

// Using String.format
String message = String.format("""
        Dear %s,
        You are %d years old.
        Welcome!
        """, name, age);

// With replace (simple cases)
String template = """
        Dear ${name},
        Welcome to ${company}!
        """.replace("${name}", name)
           .replace("${company}", "Google");
```

---

## 7. Pattern and Regex for String Matching

### 7.1 Pattern and Matcher Basics

```java
import java.util.regex.*;

// Compile pattern (reuse for performance)
Pattern pattern = Pattern.compile("\\d+"); // Match one or more digits
Matcher matcher = pattern.matcher("Hello 123 World 456");

// find() - find next match
while (matcher.find()) {
    System.out.println(matcher.group()); // "123", "456"
    System.out.println("Start: " + matcher.start()); // Start index
    System.out.println("End: " + matcher.end());     // End index (exclusive)
}

// matches() - entire string must match
Pattern.matches("\\d+", "12345");  // true
Pattern.matches("\\d+", "123abc"); // false

// Groups
Pattern p = Pattern.compile("(\\w+)@(\\w+)\\.(\\w+)");
Matcher m = p.matcher("john@email.com");
if (m.matches()) {
    m.group(0); // "john@email.com" (entire match)
    m.group(1); // "john"
    m.group(2); // "email"
    m.group(3); // "com"
}
```

### 7.2 Common Regex Patterns

```java
// Email validation
String emailRegex = "^[A-Za-z0-9+_.-]+@[A-Za-z0-9.-]+$";

// Phone number (Indian)
String phoneRegex = "^[6-9]\\d{9}$";

// Password (min 8 chars, 1 upper, 1 lower, 1 digit, 1 special)
String passRegex = "^(?=.*[a-z])(?=.*[A-Z])(?=.*\\d)(?=.*[@$!%*?&])[A-Za-z\\d@$!%*?&]{8,}$";

// IP Address
String ipRegex = "^((25[0-5]|2[0-4]\\d|[01]?\\d\\d?)\\.){3}(25[0-5]|2[0-4]\\d|[01]?\\d\\d?)$";

// URL
String urlRegex = "^(https?://)?([\\w.-]+)\\.([a-z]{2,})(:[0-9]+)?(/.*)?$";

// Date (YYYY-MM-DD)
String dateRegex = "^\\d{4}-(0[1-9]|1[0-2])-(0[1-9]|[12]\\d|3[01])$";
```

### 7.3 Regex with String Methods

```java
// String.matches() - uses Pattern.matches() internally
"hello123".matches("[a-z]+\\d+"); // true

// String.split() with regex
"one, two,  three".split(",\\s*"); // ["one", "two", "three"]

// String.replaceAll() with capturing groups
"John Smith".replaceAll("(\\w+) (\\w+)", "$2, $1"); // "Smith, John"

// Remove all non-alphanumeric
"Hello! @World #123".replaceAll("[^a-zA-Z0-9]", ""); // "HelloWorld123"

// Replace multiple spaces with single space
"Hello    World".replaceAll("\\s+", " "); // "Hello World"
```

### 7.4 Named Groups (Java 7+)

```java
Pattern p = Pattern.compile("(?<year>\\d{4})-(?<month>\\d{2})-(?<day>\\d{2})");
Matcher m = p.matcher("2024-03-15");

if (m.matches()) {
    String year = m.group("year");   // "2024"
    String month = m.group("month"); // "03"
    String day = m.group("day");     // "15"
}
```

### 7.5 Regex Flags

```java
// Case insensitive
Pattern p = Pattern.compile("hello", Pattern.CASE_INSENSITIVE);
p.matcher("HELLO").matches(); // true

// Multiline (^ and $ match line boundaries)
Pattern.compile("^\\w+$", Pattern.MULTILINE);

// Dotall (. matches newline too)
Pattern.compile(".*", Pattern.DOTALL);

// Inline flags
Pattern.compile("(?i)hello");        // Case insensitive
Pattern.compile("(?m)^start");       // Multiline
Pattern.compile("(?s).*");           // Dotall
Pattern.compile("(?imsx)pattern");   // Multiple flags
```

---

## 8. Interview Tricky Questions

### Q1: What's the output?

```java
String s1 = "Hello";
String s2 = "Hello";
String s3 = "Hel" + "lo";
String s4 = "Hel" + new String("lo");
final String s5 = "Hel";
String s6 = s5 + "lo";

System.out.println(s1 == s2);  // true  (same pool reference)
System.out.println(s1 == s3);  // true  (compile-time constant)
System.out.println(s1 == s4);  // false (runtime concatenation with new)
System.out.println(s1 == s6);  // true  (s5 is final → compile-time constant)
```

### Q2: String Pool and GC

```java
// String pool objects are NOT garbage collected easily
// They're stored in heap (Java 7+) but managed specially
// Interned strings can be GC'd if no references exist (Java 7+)

String s = new String("test").intern(); // Adds to pool
s = null; // Pool reference still exists, won't be GC'd immediately
```

### Q3: Why is String final?

```java
// If String could be subclassed:
public class MaliciousString extends String { // NOT POSSIBLE
    @Override
    public boolean equals(Object o) {
        return true; // Always equals! Security vulnerability
    }
}
// Making String final prevents this
```

### Q4: StringBuilder vs String Performance

```java
// When is + actually fine?
// Single statement with literals/variables (compiler optimizes):
String s = a + b + c + d; // Fine! Compiler uses StringBuilder or StringConcatFactory

// When is + BAD?
// In loops!
for (int i = 0; i < n; i++) {
    s += x; // Each iteration: new StringBuilder → toString → new String
}
```

### Q5: Comparing Strings with null

```java
// Always put literal first to avoid NPE
String input = null;

// BAD
input.equals("test");         // NullPointerException!

// GOOD
"test".equals(input);         // false (no NPE)

// BEST (Java 7+)
Objects.equals(input, "test"); // false (null-safe)
```
