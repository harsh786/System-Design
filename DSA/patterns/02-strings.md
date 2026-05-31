# Strings - Pattern Guide

---

## Pattern Recognition Signals

| Signal | Pattern |
|--------|---------|
| Anagram check/group | Frequency Array [26] |
| Longest palindromic substring | Expand from Center |
| Pattern matching in text | KMP / Rabin-Karp |
| Nested encoding `3[a2[c]]` | Stack-based decode |
| Serialize/deserialize list | Length + Delimiter encoding |
| Generate valid structures | Backtracking with constraints |
| Substring with char constraints | Sliding Window + Frequency |

---

## Pattern 1: Character Frequency Array

**When:** Anagram checks, character comparisons, frequency constraints.

### Template
```java
int[] freq = new int[26];
for (char c : s.toCharArray()) freq[c - 'a']++;

// Anagram check: Arrays.equals(freq1, freq2)
// Anagram grouping: use sorted string OR freq array as key
```

### Why Array over HashMap?
- No hashing overhead (direct index)
- Cache-friendly (contiguous memory)
- Fixed O(1) space (26 slots)
- Comparison: O(26) = O(1)

### Grouping Strategy
```java
// Option 1: Sorted key (O(k log k) per word)
String key = new String(sorted(word.toCharArray()));

// Option 2: Frequency key (O(k) per word)
String key = Arrays.toString(freq);  // "1#0#0#...#0"

// Option 3: Prime product (risk of overflow)
int key = 1;
for (char c : word) key *= primes[c - 'a'];
```

---

## Pattern 2: Expand from Center (Palindromes)

**When:** Longest palindromic substring, count palindromic substrings.

### Template
```java
int maxLen = 0, start = 0;
for (int center = 0; center < n; center++) {
    int len1 = expand(s, center, center);      // odd length
    int len2 = expand(s, center, center + 1);  // even length
    int len = Math.max(len1, len2);
    if (len > maxLen) {
        maxLen = len;
        start = center - (len - 1) / 2;
    }
}
return s.substring(start, start + maxLen);

int expand(String s, int l, int r) {
    while (l >= 0 && r < s.length() && s.charAt(l) == s.charAt(r)) {
        l--; r++;
    }
    return r - l - 1;
}
```

### Visualization
```
  "c b b d"
     ^ ^ expand(1,2): s[1]==s[2] ('b'=='b') → expand
   ^ ^   ^ s[0]!=s[3] → stop
   palindrome = "bb", length 2

  "r a c e c a r"
         ^ expand(3,3): 'e' alone
       ^     ^ 'c'=='c'
     ^         ^ 'a'=='a'  
   ^             ^ 'r'=='r'
   palindrome = "racecar", length 7
```

### For O(n): Manacher's Algorithm
```
Transform: "abc" → "^#a#b#c#$" (insert separators)
P[i] = radius of palindrome centered at i
Use previously computed palindromes to skip expansion
```

**Complexity:** Expand = O(n²), Manacher's = O(n)

---

## Pattern 3: Stack-Based String Decoding

**When:** Nested repetition patterns like `3[a2[c]]` → "accaccacc"

### Template
```java
Deque<StringBuilder> strStack = new ArrayDeque<>();
Deque<Integer> numStack = new ArrayDeque<>();
StringBuilder current = new StringBuilder();
int num = 0;

for (char c : s.toCharArray()) {
    if (Character.isDigit(c)) {
        num = num * 10 + (c - '0');
    } else if (c == '[') {
        strStack.push(current);
        numStack.push(num);
        current = new StringBuilder();
        num = 0;
    } else if (c == ']') {
        StringBuilder prev = strStack.pop();
        int repeat = numStack.pop();
        for (int i = 0; i < repeat; i++) prev.append(current);
        current = prev;
    } else {
        current.append(c);
    }
}
return current.toString();
```

### Trace
```
Input: "3[a2[c]]"

Step by step:
  '3' → num=3
  '[' → push("", 3), reset current=""
  'a' → current="a"
  '2' → num=2
  '[' → push("a", 2), reset current=""
  'c' → current="c"
  ']' → pop("a",2), current = "a" + "c"*2 = "acc"
  ']' → pop("",3), current = "" + "acc"*3 = "accaccacc"
```

---

## Pattern 4: KMP Pattern Matching

**When:** Find pattern in text in O(n + m), or find repeated patterns.

### LPS Array Construction
```java
// LPS[i] = length of longest proper prefix of pattern[0..i] that is also suffix
int[] lps = new int[m];
int len = 0, i = 1;
while (i < m) {
    if (pattern.charAt(i) == pattern.charAt(len)) {
        lps[i++] = ++len;
    } else {
        if (len > 0) len = lps[len - 1];  // fall back (don't advance i)
        else lps[i++] = 0;
    }
}
```

### Search
```java
int i = 0, j = 0;  // i for text, j for pattern
while (i < n) {
    if (text.charAt(i) == pattern.charAt(j)) { i++; j++; }
    if (j == m) {
        // Match found at index i - j
        j = lps[j - 1];
    } else if (i < n && text.charAt(i) != pattern.charAt(j)) {
        if (j > 0) j = lps[j - 1];
        else i++;
    }
}
```

### LPS Example
```
Pattern: "AABAACAABAA"
LPS:      [0,1,0,1,2,0,1,2,3,4,5]

Index 8: "AABAACAAB" → prefix "AAB" = suffix "AAB" → LPS=3
Index 10: "AABAACAABAA" → prefix "AABAA" = suffix "AABAA" → LPS=5

Key insight: when mismatch at j, jump to lps[j-1] (don't restart from 0)
```

**Complexity:** O(n + m) time, O(m) space

---

## Pattern 5: Rabin-Karp (Rolling Hash)

**When:** Multiple pattern matching, duplicate substrings, plagiarism detection.

### Template
```java
long base = 31, mod = 1_000_000_007;
long hash = 0, power = 1;

// Build hash of first window
for (int i = 0; i < m; i++) {
    hash = (hash * base + s.charAt(i)) % mod;
    if (i > 0) power = (power * base) % mod;
}

// Roll the window
for (int i = m; i < n; i++) {
    hash = (hash - s.charAt(i - m) * power % mod + mod) % mod;
    hash = (hash * base + s.charAt(i)) % mod;
    // Compare hash with target hash; verify on match
}
```

### Applications
- **Longest Duplicate Substring:** Binary search on length + rolling hash
- **Repeated DNA Sequences:** Hash windows of length 10
- **String matching with wildcards:** Segment-based hashing

**Complexity:** O(n) average per pattern, O(nm) worst case (hash collisions)

---

## Pattern 6: Parentheses Generation

**When:** Generate all valid combinations of n pairs.

### Template
```java
void generate(int open, int close, StringBuilder current, List<String> result) {
    if (current.length() == 2 * n) {
        result.add(current.toString());
        return;
    }
    if (open < n) {
        current.append('(');
        generate(open + 1, close, current, result);
        current.deleteCharAt(current.length() - 1);
    }
    if (close < open) {  // KEY: only close if there's an unmatched open
        current.append(')');
        generate(open, close + 1, current, result);
        current.deleteCharAt(current.length() - 1);
    }
}
```

### Decision Tree for n=3
```
                        ""
                    /        
                  "("         
               /       \
           "(("         "()"
          /    \          |
       "((("   "(()"    "()("
         |     / \        |
      "((()""(()(" "(())" "()(("
         |     |     |      |
         ...  ...   ...    ...

Valid results: ((())), (())(), ()(()),  ()(()), ()()()
Count: C(n) = (2n)! / ((n+1)! * n!)  [Catalan number]
```

---

## Pattern 7: Two Pointer on String

**When:** Valid palindrome (with non-alphanumeric), compare strings.

### Template
```java
int left = 0, right = s.length() - 1;
while (left < right) {
    while (left < right && !Character.isLetterOrDigit(s.charAt(left))) left++;
    while (left < right && !Character.isLetterOrDigit(s.charAt(right))) right--;
    if (Character.toLowerCase(s.charAt(left)) != Character.toLowerCase(s.charAt(right)))
        return false;
    left++; right--;
}
return true;
```

---

## Pattern 8: String to Integer (Edge Case Handling)

**When:** Implement atoi with all edge cases.

### Checklist
```java
int i = 0, sign = 1, result = 0;
// 1. Skip whitespace
while (i < n && s.charAt(i) == ' ') i++;
// 2. Handle sign
if (i < n && (s.charAt(i) == '+' || s.charAt(i) == '-'))
    sign = s.charAt(i++) == '-' ? -1 : 1;
// 3. Process digits with overflow check
while (i < n && Character.isDigit(s.charAt(i))) {
    int digit = s.charAt(i) - '0';
    if (result > (Integer.MAX_VALUE - digit) / 10)
        return sign == 1 ? Integer.MAX_VALUE : Integer.MIN_VALUE;
    result = result * 10 + digit;
    i++;
}
return result * sign;
```

---

## Pattern 9: Longest Substring Without Repeating (Sliding Window)

**When:** Longest substring with unique characters.

### Template
```java
int[] lastSeen = new int[128];
Arrays.fill(lastSeen, -1);
int maxLen = 0, left = 0;

for (int right = 0; right < n; right++) {
    char c = s.charAt(right);
    if (lastSeen[c] >= left) {
        left = lastSeen[c] + 1;  // jump past duplicate
    }
    lastSeen[c] = right;
    maxLen = Math.max(maxLen, right - left + 1);
}
return maxLen;
```

### Visualization
```
"a b c a b c b b"
 ^         ^       left=0, right=3: 'a' seen at 0 → left=1
   ^       ^       left=1, right=4: 'b' seen at 1 → left=2
     ^     ^       left=2, right=5: 'c' seen at 2 → left=3
       ^   ^       maxLen so far = 3
```

---

## Summary Decision Flowchart

```
String Problem?
│
├─ Anagram/frequency? ──────────→ Frequency Array[26]
│
├─ Palindrome? ─────────────────→ Expand from Center (or DP)
│
├─ Pattern in text? ────────────→ KMP or Rabin-Karp
│
├─ Nested encoding? ────────────→ Stack decode
│
├─ Valid/generate brackets? ────→ Backtracking with open/close count
│
├─ Substring with constraint? ──→ Sliding Window
│
├─ Compare two strings? ────────→ Two Pointer or DP (edit distance)
│
└─ Parse number/expression? ────→ Sequential processing with checks
```
