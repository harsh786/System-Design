# String Patterns

---

## Pattern 1: Character Frequency Array [26]

**Signal:** Anagram checks, character counting, grouping strings by composition, comparing character distributions without sorting.

**Template:**

```java
// Anagram check
public boolean isAnagram(String s, String t) {
    if (s.length() != t.length()) return false;
    int[] freq = new int[26];
    for (int i = 0; i < s.length(); i++) {
        freq[s.charAt(i) - 'a']++;
        freq[t.charAt(i) - 'a']--;
    }
    for (int count : freq) {
        if (count != 0) return false;
    }
    return true;
}

// Group Anagrams
public List<List<String>> groupAnagrams(String[] strs) {
    Map<String, List<String>> map = new HashMap<>();
    for (String s : strs) {
        int[] freq = new int[26];
        for (char c : s.toCharArray()) freq[c - 'a']++;
        String key = Arrays.toString(freq);  // deterministic key
        map.computeIfAbsent(key, k -> new ArrayList<>()).add(s);
    }
    return new ArrayList<>(map.values());
}
```

**Visualization:**

```
String: "anagram"

freq[0] = 3  (a)
freq[6] = 1  (g)
freq[12]= 1  (m)
freq[13]= 1  (n)
freq[17]= 1  (r)

Index:  0  1  2  3  4  5  6  7 ... 12 13 ... 17 ... 25
Value: [3, 0, 0, 0, 0, 0, 1, 0 ...  1, 1 ...  1 ...  0]
        a  b  c  d  e  f  g  h      m  n      r      z

Key insight: Two strings are anagrams iff their freq arrays are identical.
```

**Variants:**
- Sliding window anagram (LC 438): maintain freq diff in window of size |p|
- Minimum window substring (LC 76): freq array + "have/need" counters
- Close strings (LC 1657): compare sorted frequency distributions

**Complexity:** O(n) time, O(1) space (fixed 26-size array)

---

## Pattern 2: Expand from Center

**Signal:** Palindrome detection, longest palindromic substring, counting palindromic substrings. Any problem needing all palindromes centered at each position.

**Template:**

```java
public String longestPalindrome(String s) {
    int start = 0, maxLen = 0;
    for (int i = 0; i < s.length(); i++) {
        int len1 = expand(s, i, i);     // odd length
        int len2 = expand(s, i, i + 1); // even length
        int len = Math.max(len1, len2);
        if (len > maxLen) {
            maxLen = len;
            start = i - (len - 1) / 2;
        }
    }
    return s.substring(start, start + maxLen);
}

private int expand(String s, int left, int right) {
    while (left >= 0 && right < s.length() && s.charAt(left) == s.charAt(right)) {
        left--;
        right++;
    }
    return right - left - 1;  // length of palindrome
}

// Count all palindromic substrings
public int countSubstrings(String s) {
    int count = 0;
    for (int i = 0; i < s.length(); i++) {
        count += countExpand(s, i, i);
        count += countExpand(s, i, i + 1);
    }
    return count;
}

private int countExpand(String s, int l, int r) {
    int count = 0;
    while (l >= 0 && r < s.length() && s.charAt(l) == s.charAt(r)) {
        count++;
        l--;
        r++;
    }
    return count;
}
```

**Visualization:**

```
String: "babad"

Center at index 1 (odd):        Center at index 2 (odd):
    expand(s, 1, 1)                 expand(s, 2, 2)
    
    b [a] b a d                     b a [b] a d
      L=R=1                           L=R=2
    
   [b  a  b] a d                   b [a  b  a] d
    L=0    R=2                      L=1      R=3
    match! len=3 "bab"              match! len=3 "aba"

   expand stops at                  [b  a  b  a] d
   L=-1 (out of bounds)             L=0      R=4
                                    'b' != 'd', stop. len=3

2n-1 possible centers (n odd + n-1 even) => O(n^2) total
```

**Variants:**
- Manacher's Algorithm: O(n) but rarely needed in interviews
- Palindromic partitioning: expand + DP
- Shortest palindrome (LC 214): expand from start / KMP trick

**Complexity:** O(n^2) time, O(1) space

---

## Pattern 3: Stack-Based Decode

**Signal:** Nested structure with repetition counts, bracket matching with accumulated context, recursive string encoding like `3[a2[c]]`.

**Template:**

```java
public String decodeString(String s) {
    Deque<StringBuilder> strStack = new ArrayDeque<>();
    Deque<Integer> numStack = new ArrayDeque<>();
    StringBuilder current = new StringBuilder();
    int num = 0;

    for (char c : s.toCharArray()) {
        if (Character.isDigit(c)) {
            num = num * 10 + (c - '0');
        } else if (c == '[') {
            numStack.push(num);
            strStack.push(current);
            current = new StringBuilder();
            num = 0;
        } else if (c == ']') {
            int repeat = numStack.pop();
            StringBuilder prev = strStack.pop();
            for (int i = 0; i < repeat; i++) {
                prev.append(current);
            }
            current = prev;
        } else {
            current.append(c);
        }
    }
    return current.toString();
}
```

**Visualization:**

```
Input: "3[a2[c]]"

Step-by-step stack trace:

Char  | numStack | strStack    | current | num
------+----------+-------------+---------+----
'3'   | []       | []          | ""      | 3
'['   | [3]      | [""]        | ""      | 0
'a'   | [3]      | [""]        | "a"     | 0
'2'   | [3]      | [""]        | "a"     | 2
'['   | [3,2]    | ["","a"]    | ""      | 0
'c'   | [3,2]    | ["","a"]    | "c"     | 0
']'   | [3]      | [""]        | "acc"   | 0
       pop 2, pop "a" => "a" + "c"*2 = "acc"
']'   | []       | []          | "accaccacc" | 0
       pop 3, pop "" => "" + "acc"*3 = "accaccacc"

Output: "accaccacc"
```

**Variants:**
- Basic calculator (LC 224/227): stack for operators + parentheses
- Nested list deserialization (LC 385)
- Brace expansion (LC 1087): stack + cartesian product
- Atom count in formula (LC 726): stack of maps

**Complexity:** O(n * maxRepeat) time, O(n) space for stack depth

---

## Pattern 4: KMP Pattern Matching

**Signal:** Find pattern in text in O(n+m), repeated pattern detection, shortest repeating unit, string period problems.

**Template:**

```java
// Build LPS (Longest Proper Prefix which is also Suffix) array
private int[] buildLPS(String pattern) {
    int m = pattern.length();
    int[] lps = new int[m];
    int len = 0;  // length of previous longest prefix suffix
    int i = 1;

    while (i < m) {
        if (pattern.charAt(i) == pattern.charAt(len)) {
            len++;
            lps[i] = len;
            i++;
        } else {
            if (len != 0) {
                len = lps[len - 1];  // don't increment i
            } else {
                lps[i] = 0;
                i++;
            }
        }
    }
    return lps;
}

// KMP Search
public int strStr(String text, String pattern) {
    int n = text.length(), m = pattern.length();
    if (m == 0) return 0;
    int[] lps = buildLPS(pattern);
    int i = 0, j = 0;

    while (i < n) {
        if (text.charAt(i) == pattern.charAt(j)) {
            i++;
            j++;
        }
        if (j == m) {
            return i - j;  // found at index i-j
            // j = lps[j-1]; // for all occurrences
        } else if (i < n && text.charAt(i) != pattern.charAt(j)) {
            if (j != 0) {
                j = lps[j - 1];
            } else {
                i++;
            }
        }
    }
    return -1;
}

// Repeated substring pattern: s consists of copies of a substring
public boolean repeatedSubstringPattern(String s) {
    int[] lps = buildLPS(s);
    int n = s.length();
    int suffixLen = lps[n - 1];
    // Period = n - suffixLen. If period divides n, it's repeating.
    return suffixLen > 0 && n % (n - suffixLen) == 0;
}
```

**Visualization:**

```
Pattern: "ABABCABAB"
Building LPS:

Index:    0  1  2  3  4  5  6  7  8
Pattern:  A  B  A  B  C  A  B  A  B
LPS:     [0, 0, 1, 2, 0, 1, 2, 3, 4]

LPS[8]=4 means "ABAB" is both prefix and suffix of "ABABCABAB"

KMP Search: text="ABABDABABCABABAB", pattern="ABABCABAB"

    A B A B D A B A B C A B A B A B
    A B A B C               <-- mismatch at j=4
              ^             lps[3]=2, so j=2
        A B A B C           <-- mismatch at j=0
              ^             j=0, advance i
              A B A B C A B A B    <-- MATCH at i=5!
```

**Variants:**
- All occurrences: continue with `j = lps[j-1]` after match
- Shortest palindrome (LC 214): KMP on `s + "#" + reverse(s)`
- Repeated string match (LC 686): concatenate + KMP

**Complexity:** O(n + m) time, O(m) space for LPS array

---

## Pattern 5: Rabin-Karp Rolling Hash

**Signal:** Multiple pattern search, finding duplicate substrings of length k, plagiarism detection, longest duplicate substring (binary search + hash).

**Template:**

```java
public int rabinKarp(String text, String pattern) {
    int n = text.length(), m = pattern.length();
    if (m > n) return -1;

    long MOD = 1_000_000_007L;
    long BASE = 31L;
    long power = 1; // BASE^(m-1) % MOD

    for (int i = 0; i < m - 1; i++) {
        power = (power * BASE) % MOD;
    }

    // Compute pattern hash and initial window hash
    long patHash = 0, winHash = 0;
    for (int i = 0; i < m; i++) {
        patHash = (patHash * BASE + pattern.charAt(i)) % MOD;
        winHash = (winHash * BASE + text.charAt(i)) % MOD;
    }

    for (int i = 0; i <= n - m; i++) {
        if (winHash == patHash) {
            // Verify to avoid hash collision
            if (text.substring(i, i + m).equals(pattern)) return i;
        }
        if (i < n - m) {
            // Roll: remove leftmost, add new rightmost
            winHash = (winHash - text.charAt(i) * power % MOD + MOD) % MOD;
            winHash = (winHash * BASE + text.charAt(i + m)) % MOD;
        }
    }
    return -1;
}

// Longest Duplicate Substring (binary search + rolling hash)
public String longestDupSubstring(String s) {
    int lo = 1, hi = s.length() - 1;
    String result = "";
    while (lo <= hi) {
        int mid = lo + (hi - lo) / 2;
        String dup = findDuplicate(s, mid);
        if (dup != null) {
            result = dup;
            lo = mid + 1;
        } else {
            hi = mid - 1;
        }
    }
    return result;
}

private String findDuplicate(String s, int len) {
    long MOD = (1L << 61) - 1; // Mersenne prime for fewer collisions
    long BASE = 31;
    long hash = 0, power = 1;

    for (int i = 0; i < len; i++) {
        hash = (hash * BASE + s.charAt(i)) % MOD;
        if (i < len - 1) power = (power * BASE) % MOD;
    }

    Map<Long, Integer> seen = new HashMap<>();
    seen.put(hash, 0);

    for (int i = 1; i <= s.length() - len; i++) {
        hash = (hash - s.charAt(i - 1) * power % MOD + MOD) % MOD;
        hash = (hash * BASE + s.charAt(i + len - 1)) % MOD;
        if (seen.containsKey(hash)) {
            int prev = seen.get(hash);
            String candidate = s.substring(i, i + len);
            if (candidate.equals(s.substring(prev, prev + len))) return candidate;
        }
        seen.put(hash, i);
    }
    return null;
}
```

**Visualization:**

```
Rolling Hash concept:

Text:    "a b c d e f"    BASE=31, window size=3
          -------
Window 1: hash("abc") = a*31^2 + b*31^1 + c*31^0

Slide right:
          ---------
Window 2: hash("bcd") = (hash("abc") - a*31^2) * 31 + d

General:  newHash = (oldHash - leftChar * BASE^(m-1)) * BASE + rightChar

Why rolling?  Recomputing hash each time = O(m) per position = O(nm) total
              Rolling hash = O(1) per position = O(n) total

Collision handling:
  hash("abc") == hash("xyz") possible!  (birthday paradox)
  Always verify with actual string comparison on hash match.
  Use double hashing or large prime for competitive programming.
```

**Variants:**
- Multiple pattern search: hash all patterns, check window against set
- Longest common substring of two strings: binary search + hash sets
- Repeated DNA sequences (LC 187): fixed window + hash set

**Complexity:** O(n) average, O(nm) worst case (many collisions). Space O(n) for hash map.

---

## Pattern 6: Parentheses Generation

**Signal:** Generate all valid combinations, backtracking with balance constraints, any problem with open/close pairing where `open >= close` invariant must hold.

**Template:**

```java
public List<String> generateParenthesis(int n) {
    List<String> result = new ArrayList<>();
    backtrack(result, new StringBuilder(), 0, 0, n);
    return result;
}

private void backtrack(List<String> result, StringBuilder sb,
                       int open, int close, int n) {
    if (sb.length() == 2 * n) {
        result.add(sb.toString());
        return;
    }
    if (open < n) {
        sb.append('(');
        backtrack(result, sb, open + 1, close, n);
        sb.deleteCharAt(sb.length() - 1);
    }
    if (close < open) {
        sb.append(')');
        backtrack(result, sb, open, close + 1, n);
        sb.deleteCharAt(sb.length() - 1);
    }
}
```

**Visualization:**

```
n = 2, Decision Tree:

                     ""
                   open=0, close=0
                     |
                    "("
                  open=1, close=0
                /              \
           "(("                "()"
         o=2,c=0             o=1,c=1
            |                   |
          "(()"              "()("
         o=2,c=1            o=2,c=1
            |                   |
          "(())"             "()()"
         o=2,c=2            o=2,c=2
          VALID              VALID

Constraints enforced at each node:
  - Can add '(' if open < n
  - Can add ')' if close < open  (ensures validity)

Result count = Catalan number C(n) = (2n)! / ((n+1)! * n!)
For n=3: 5 results, n=4: 14 results
```

**Variants:**
- Valid parentheses check (LC 20): stack-based, O(n)
- Longest valid parentheses (LC 32): stack or DP
- Remove invalid parentheses (LC 301): BFS for minimum removals
- Different bracket types: extend constraints per type

**Complexity:** O(4^n / sqrt(n)) time (Catalan number), O(n) space for recursion

---

## Pattern 7: Two-Pointer on String

**Signal:** Palindrome validation, comparing from both ends, skipping characters, in-place transformations, converging checks.

**Template:**

```java
// Valid Palindrome (ignore non-alphanumeric)
public boolean isPalindrome(String s) {
    int left = 0, right = s.length() - 1;
    while (left < right) {
        while (left < right && !Character.isLetterOrDigit(s.charAt(left))) {
            left++;
        }
        while (left < right && !Character.isLetterOrDigit(s.charAt(right))) {
            right--;
        }
        if (Character.toLowerCase(s.charAt(left)) !=
            Character.toLowerCase(s.charAt(right))) {
            return false;
        }
        left++;
        right--;
    }
    return true;
}

// Valid Palindrome II (can delete at most one char)
public boolean validPalindrome(String s) {
    int l = 0, r = s.length() - 1;
    while (l < r) {
        if (s.charAt(l) != s.charAt(r)) {
            return isPalinRange(s, l + 1, r) || isPalinRange(s, l, r - 1);
        }
        l++;
        r--;
    }
    return true;
}

private boolean isPalinRange(String s, int l, int r) {
    while (l < r) {
        if (s.charAt(l++) != s.charAt(r--)) return false;
    }
    return true;
}
```

**Visualization:**

```
Input: "A man, a plan, a canal: Panama"

After filtering: "amanaplanacanalpanama"

 l                                r
 a m a n a p l a n a c a n a l p a n a m a
 ^                                       ^
 a == a  ->  move inward

   l                            r
 a m a n a p l a n a c a n a l p a n a m a
   ^                                   ^
   m == m  ->  move inward

     ... converge to center -> VALID

Valid Palindrome II (delete one):
"abca"
 l      r
 a      a  ->  match
  l   r
  b   c   ->  mismatch!
       Branch 1: skip l -> "ca" palindrome? NO
       Branch 2: skip r -> "bc" palindrome? NO
  Wait: check "bc"(l+1,r) = "c"? No. check "ab"(l,r-1) = "b"? 
  Actually: isPalin("bc") = false, isPalin("ab") = false... 
  Correction: isPalin(s, 1, 2)="bc" false, isPalin(s, 1, 2)... 
  
  "abca": l=1('b'), r=2('c') mismatch
    try skip l: isPalin(s,2,2) "c" -> true! VALID
```

**Variants:**
- Reverse vowels only (LC 345)
- Container with most water adapted to strings
- Minimum deletions to make palindrome: two-pointer + LCS

**Complexity:** O(n) time, O(1) space

---

## Pattern 8: String to Integer (atoi)

**Signal:** Parsing numeric strings, handling whitespace/sign/overflow, state machine for tokenization, any string-to-number conversion.

**Template:**

```java
public int myAtoi(String s) {
    int i = 0, n = s.length();
    
    // 1. Skip whitespace
    while (i < n && s.charAt(i) == ' ') i++;
    if (i == n) return 0;

    // 2. Handle sign
    int sign = 1;
    if (s.charAt(i) == '+' || s.charAt(i) == '-') {
        sign = (s.charAt(i) == '-') ? -1 : 1;
        i++;
    }

    // 3. Convert digits with overflow check
    int result = 0;
    while (i < n && Character.isDigit(s.charAt(i))) {
        int digit = s.charAt(i) - '0';

        // Overflow check BEFORE multiplication
        if (result > (Integer.MAX_VALUE - digit) / 10) {
            return (sign == 1) ? Integer.MAX_VALUE : Integer.MIN_VALUE;
        }
        result = result * 10 + digit;
        i++;
    }

    return result * sign;
}
```

**Visualization:**

```
Input: "   -042abc"

State machine:

  [WHITESPACE] --non-space--> [SIGN] --digit--> [DIGITS] --non-digit--> [END]
       |                        |                   |
    skip ' '              optional +/-         accumulate
                                              + overflow check

Step trace:
  i=0: ' ' skip
  i=1: ' ' skip  
  i=2: ' ' skip
  i=3: '-' sign = -1
  i=4: '0' result = 0*10+0 = 0
  i=5: '4' result = 0*10+4 = 4
  i=6: '2' result = 4*10+2 = 42
  i=7: 'a' not digit, STOP

  return 42 * -1 = -42

Overflow check logic:
  Before: result = result * 10 + digit
  If result > (MAX_VALUE - digit) / 10, then overflow.
  
  Example: MAX_VALUE = 2147483647
  If result = 214748365 and digit = 0:
    214748365 > (2147483647 - 0) / 10 = 214748364  -> OVERFLOW!
```

**Variants:**
- String to double: handle decimal point + exponent
- Roman to integer (LC 13): lookup + subtraction rule
- Integer to English words (LC 273): chunk by thousands
- Finite state machine approach: explicit states enum

**Complexity:** O(n) time, O(1) space

---

## Pattern 9: Encode/Decode Strings

**Signal:** Serialization of string lists, length-prefix protocols, delimiter handling when strings can contain any character, network protocol design.

**Template:**

```java
// Encode: "hello","world" -> "5#hello5#world"
public String encode(List<String> strs) {
    StringBuilder sb = new StringBuilder();
    for (String s : strs) {
        sb.append(s.length()).append('#').append(s);
    }
    return sb.toString();
}

// Decode: "5#hello5#world" -> ["hello","world"]
public List<String> decode(String str) {
    List<String> result = new ArrayList<>();
    int i = 0;
    while (i < str.length()) {
        int j = i;
        while (str.charAt(j) != '#') j++;
        int len = Integer.parseInt(str.substring(i, j));
        String word = str.substring(j + 1, j + 1 + len);
        result.add(word);
        i = j + 1 + len;
    }
    return result;
}
```

**Visualization:**

```
Encode: ["hello", "wor#ld", "", "hi"]

  "hello"  -> "5#hello"
  "wor#ld" -> "6#wor#ld"    <-- '#' in content is safe!
  ""       -> "0#"
  "hi"     -> "2#hi"

Encoded: "5#hello6#wor#ld0#2#hi"

Decode walkthrough:
  i=0: scan to '#' at j=1 -> len=5 -> extract [2..7) = "hello" -> i=7
  i=7: scan to '#' at j=8 -> len=6 -> extract [9..15) = "wor#ld" -> i=15
  i=15: scan to '#' at j=16 -> len=0 -> extract [17..17) = "" -> i=17
  i=17: scan to '#' at j=18 -> len=2 -> extract [19..21) = "hi" -> i=21

Key insight: length prefix makes ANY delimiter in content safe.
             We always know exactly how many chars to read.

Alternative approaches (inferior):
  - Escaping: "\#" doubles complexity, error-prone
  - Fixed delimiter: fails if content contains delimiter
  - Chunked encoding: HTTP-style, more overhead
```

**Variants:**
- Fixed-width length header: `0005hello0006wor#ld` (simpler parsing)
- Codec for nested structures: recursive length-prefix
- Compression: run-length encoding `aaabbb` -> `3a3b`
- URL encoding: percent-encoding for special characters

**Complexity:** O(n) time for both encode/decode, O(n) space for output

---

## Pattern 10: Longest Substring Without Repeating Characters

**Signal:** Sliding window on strings, tracking last occurrence, maximum window with distinct constraint, any "longest/shortest substring with property" problem.

**Template:**

```java
public int lengthOfLongestSubstring(String s) {
    int[] lastSeen = new int[128]; // ASCII
    Arrays.fill(lastSeen, -1);
    int maxLen = 0, left = 0;

    for (int right = 0; right < s.length(); right++) {
        char c = s.charAt(right);
        if (lastSeen[c] >= left) {
            left = lastSeen[c] + 1;  // jump left past duplicate
        }
        lastSeen[c] = right;
        maxLen = Math.max(maxLen, right - left + 1);
    }
    return maxLen;
}

// Generic template: Longest substring with at most K distinct chars
public int lengthOfLongestSubstringKDistinct(String s, int k) {
    Map<Character, Integer> window = new HashMap<>();
    int left = 0, maxLen = 0;

    for (int right = 0; right < s.length(); right++) {
        window.merge(s.charAt(right), 1, Integer::sum);

        while (window.size() > k) {
            char lc = s.charAt(left);
            window.merge(lc, -1, Integer::sum);
            if (window.get(lc) == 0) window.remove(lc);
            left++;
        }
        maxLen = Math.max(maxLen, right - left + 1);
    }
    return maxLen;
}
```

**Visualization:**

```
Input: "abcabcbb"

lastSeen initialized to all -1, left=0

right=0: 'a' lastSeen['a']=-1 < left(0), no jump. lastSeen['a']=0. len=1
right=1: 'b' lastSeen['b']=-1 < left(0), no jump. lastSeen['b']=1. len=2
right=2: 'c' lastSeen['c']=-1 < left(0), no jump. lastSeen['c']=2. len=3
right=3: 'a' lastSeen['a']=0 >= left(0), JUMP left=1. lastSeen['a']=3. len=3
right=4: 'b' lastSeen['b']=1 >= left(1), JUMP left=2. lastSeen['b']=4. len=3
right=5: 'c' lastSeen['c']=2 >= left(2), JUMP left=3. lastSeen['c']=5. len=3
right=6: 'b' lastSeen['b']=4 >= left(3), JUMP left=5. lastSeen['b']=6. len=2
right=7: 'b' lastSeen['b']=6 >= left(5), JUMP left=7. lastSeen['b']=7. len=1

         a  b  c  a  b  c  b  b
         0  1  2  3  4  5  6  7
Window:  [-------]                 max=3 "abc"
            [-------]              max=3
               [-------]           max=3
                  [-------]        max=3
                        [-]        shrinking

Answer: 3

Key insight: lastSeen[c] >= left means 'c' is IN current window.
             Jump left directly (no shrink loop needed) -> O(n) guaranteed.
```

**Variants:**
- Longest with at most 2 distinct (LC 159): use HashMap
- Longest with at most K distinct (LC 340): same pattern
- Minimum window substring (LC 76): shrink when valid, expand when invalid
- Longest repeating character replacement (LC 424): window + maxFreq trick

**Complexity:** O(n) time, O(min(n, charset)) space

---

## Decision Flowchart

```
                         STRING PROBLEM
                              |
              +---------------+----------------+
              |               |                |
     Character-based?    Pattern/Match?    Structure?
              |               |                |
     +--------+------+    +--+--+       +-----+------+
     |        |      |    |     |       |     |      |
  Frequency  Two   Parse  KMP  Rabin   Stack  Encode Generate
   Array    Pointer       Karp         Decode
     |        |      |    |     |       |     |      |
     v        v      v    v     v       v     v      v

  [Anagram]  [Palindrome] [atoi]       [Nested] [Serialize] [Parentheses]
  [Grouping] [Valid w/    [Overflow]   [Decode] [Length     [Backtrack
  [Window     skip]                    string]   prefix]     open/close]
   anagram]

  +------ Substring with property? ------+
  |                                       |
  Distinct chars constraint?        Palindrome substring?
  |                                       |
  v                                       v
  Sliding Window + lastSeen       Expand from Center
  (Pattern 10)                    (Pattern 2)


QUICK DECISION TABLE:
+-------------------------------+----------------------------+
| If you see...                 | Use Pattern...             |
+-------------------------------+----------------------------+
| "anagram", "permutation"     | #1 Frequency Array         |
| "palindrome substring"       | #2 Expand from Center      |
| "decode", "nested brackets"  | #3 Stack-Based Decode      |
| "find pattern in text"       | #4 KMP                     |
| "duplicate substring len k"  | #5 Rabin-Karp              |
| "generate all valid ()"      | #6 Parentheses Generation  |
| "valid palindrome + skip"    | #7 Two-Pointer             |
| "string to integer"          | #8 atoi Parsing            |
| "serialize list of strings"  | #9 Encode/Decode           |
| "longest without repeating"  | #10 Sliding Window         |
+-------------------------------+----------------------------+

COMPLEXITY SUMMARY:
+----------+------------+--------+
| Pattern  | Time       | Space  |
+----------+------------+--------+
| #1       | O(n)       | O(1)   |
| #2       | O(n^2)     | O(1)   |
| #3       | O(n*k)     | O(n)   |
| #4       | O(n+m)     | O(m)   |
| #5       | O(n) avg   | O(n)   |
| #6       | O(4^n/sqn) | O(n)   |
| #7       | O(n)       | O(1)   |
| #8       | O(n)       | O(1)   |
| #9       | O(n)       | O(n)   |
| #10      | O(n)       | O(1)   |
+----------+------------+--------+
```
