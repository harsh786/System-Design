# 33. String Matching / String Algorithms

## Decision Flowchart

```
String Matching Problem?
│
├─ Single pattern in text?
│   ├─ Pattern length small → KMP (O(n+m), no hash collisions)
│   ├─ Need avg-case speed → Rabin-Karp (rolling hash)
│   └─ Need all occurrences + prefix info → Z-Algorithm
│
├─ Multiple patterns in text?
│   ├─ Fixed dictionary → Aho-Corasick (Trie + failure links)
│   └─ Variable patterns → Rabin-Karp (multi-hash)
│
├─ Palindrome problems?
│   ├─ Longest palindromic SUBSTRING → Manacher's / Expand Around Center
│   ├─ Longest palindromic SUBSEQUENCE → DP (2D)
│   └─ Shortest palindrome (prepend) → KMP trick (s + "#" + rev(s))
│
├─ Pattern with wildcards / regex?
│   ├─ '.' and '*' → Regular Expression DP
│   └─ '?' and '*' → Wildcard Matching DP
│
├─ Substring comparison / deduplication?
│   ├─ O(1) substring equality → String Hashing (polynomial rolling)
│   └─ Suffix-based queries (LCP, repeated substrings) → Suffix Array
│
└─ Repeated substring detection?
    └─ KMP (check if n % (n - lps[n-1]) == 0) / String doubling
```

## Algorithm Selection Table

| Scenario | Best Algorithm | Time | Space |
|----------|---------------|------|-------|
| Single exact pattern | KMP | O(n+m) | O(m) |
| Single pattern (avg case) | Rabin-Karp | O(n+m) avg | O(1) |
| All pattern positions | Z-Algorithm | O(n+m) | O(n+m) |
| Multi-pattern search | Aho-Corasick | O(n + m + z) | O(m*k) |
| Multi-pattern (simple) | Rabin-Karp | O(n*k) avg | O(k) |
| Longest palindromic substring | Manacher's | O(n) | O(n) |
| Longest palindromic subsequence | DP | O(n^2) | O(n^2) |
| Regex matching | DP | O(n*m) | O(n*m) |
| Wildcard matching | DP | O(n*m) | O(m) |
| O(1) substring compare | Polynomial Hashing | O(n) pre / O(1) query | O(n) |
| Repeated substrings / LCP | Suffix Array + LCP | O(n log n) | O(n) |
| Shortest palindrome | KMP trick | O(n) | O(n) |
| Repeated substring pattern | KMP / doubling | O(n) | O(n) |

*n = text length, m = pattern length, k = number of patterns, z = total matches*

---

## 1. KMP Algorithm (Knuth-Morris-Pratt)

### Signal
- Find pattern in text in O(n+m) guaranteed
- "Find all occurrences of pattern in string"
- Need to avoid backtracking in text

### KMP Failure Function (LPS) Construction Trace

```
Pattern: "ABABCABAB"
Index:    0 1 2 3 4 5 6 7 8

Step-by-step LPS construction:
i=1: pat[1]='B' vs pat[0]='A' → mismatch, len=0 → lps[1]=0
i=2: pat[2]='A' vs pat[0]='A' → match, len=1    → lps[2]=1
i=3: pat[3]='B' vs pat[1]='B' → match, len=2    → lps[3]=2
i=4: pat[4]='C' vs pat[2]='A' → mismatch
     fallback: len=lps[1]=0
     pat[4]='C' vs pat[0]='A' → mismatch, len=0 → lps[4]=0
i=5: pat[5]='A' vs pat[0]='A' → match, len=1    → lps[5]=1
i=6: pat[6]='B' vs pat[1]='B' → match, len=2    → lps[6]=2
i=7: pat[7]='A' vs pat[2]='A' → match, len=3    → lps[7]=3
i=8: pat[8]='B' vs pat[3]='B' → match, len=4    → lps[8]=4

Result: lps = [0, 0, 1, 2, 0, 1, 2, 3, 4]

Meaning: lps[i] = length of longest proper prefix of pat[0..i]
         which is also a suffix of pat[0..i]
```

### Template (Java)

```java
// Build LPS (failure function) array
int[] buildLPS(String pattern) {
    int m = pattern.length();
    int[] lps = new int[m];
    int len = 0; // length of previous longest prefix-suffix
    int i = 1;
    
    while (i < m) {
        if (pattern.charAt(i) == pattern.charAt(len)) {
            len++;
            lps[i] = len;
            i++;
        } else {
            if (len != 0) {
                len = lps[len - 1]; // fallback — do NOT increment i
            } else {
                lps[i] = 0;
                i++;
            }
        }
    }
    return lps;
}

// KMP Search — returns all starting indices of pattern in text
List<Integer> kmpSearch(String text, String pattern) {
    List<Integer> result = new ArrayList<>();
    int n = text.length(), m = pattern.length();
    int[] lps = buildLPS(pattern);
    
    int i = 0; // index in text
    int j = 0; // index in pattern
    
    while (i < n) {
        if (text.charAt(i) == pattern.charAt(j)) {
            i++;
            j++;
        }
        if (j == m) {
            result.add(i - j); // match found at index i-j
            j = lps[j - 1];   // continue searching
        } else if (i < n && text.charAt(i) != pattern.charAt(j)) {
            if (j != 0) {
                j = lps[j - 1]; // use failure function
            } else {
                i++;
            }
        }
    }
    return result;
}
```

### Visualization

```
Text:    "ABABDABABCABABCABAB"
Pattern: "ABABCABAB"
LPS:     [0,0,1,2,0,1,2,3,4]

     A B A B D A B A B C A B A B C A B A B
     A B A B C                               ← mismatch at i=4, j=4
             ↓ j = lps[3] = 2 (skip "AB")
         A B A B C A B A B                   ← match found at index 5!
                         ↓ j = lps[8] = 4
                 A B A B C A B A B           ← match found at index 9!
```

### Complexity
- **Time:** O(n + m) — preprocessing O(m), search O(n)
- **Space:** O(m) for LPS array

---

## 2. Rabin-Karp Algorithm

### Signal
- Average-case O(n+m) pattern matching
- Multiple pattern search (same length)
- Plagiarism detection / substring fingerprinting

### Rolling Hash Collision Handling

```
Strategy 1: Double hashing (two different bases/mods)
  - P(collision) ≈ 1/mod² ≈ 10⁻¹⁸ with two large primes
  
Strategy 2: On hash match, verify character-by-character
  - Worst case O(nm) but extremely rare with good hash

Recommended parameters:
  - base = 31 (for lowercase) or 256 (ASCII)
  - mod  = 1_000_000_007 (large prime)
  - For safety: use two mods (1e9+7, 1e9+9)
```

### Template (Java)

```java
// Single pattern Rabin-Karp
List<Integer> rabinKarp(String text, String pattern) {
    List<Integer> result = new ArrayList<>();
    int n = text.length(), m = pattern.length();
    if (m > n) return result;
    
    long BASE = 31, MOD = 1_000_000_007;
    
    // Compute base^(m-1) % MOD
    long power = 1;
    for (int i = 0; i < m - 1; i++)
        power = (power * BASE) % MOD;
    
    // Compute hash of pattern and first window
    long patHash = 0, winHash = 0;
    for (int i = 0; i < m; i++) {
        patHash = (patHash * BASE + pattern.charAt(i)) % MOD;
        winHash = (winHash * BASE + text.charAt(i)) % MOD;
    }
    
    for (int i = 0; i <= n - m; i++) {
        if (patHash == winHash) {
            // Verify to handle collision
            if (text.substring(i, i + m).equals(pattern))
                result.add(i);
        }
        // Slide window: remove leading char, add trailing char
        if (i < n - m) {
            winHash = (winHash - text.charAt(i) * power % MOD + MOD) % MOD;
            winHash = (winHash * BASE + text.charAt(i + m)) % MOD;
        }
    }
    return result;
}

// Multi-pattern Rabin-Karp (all patterns same length)
Set<Integer> rabinKarpMulti(String text, Set<String> patterns) {
    Set<Integer> result = new HashSet<>();
    if (patterns.isEmpty()) return result;
    
    int m = patterns.iterator().next().length();
    int n = text.length();
    long BASE = 31, MOD = 1_000_000_007;
    
    // Precompute pattern hashes
    Set<Long> patHashes = new HashSet<>();
    for (String p : patterns) {
        long h = 0;
        for (char c : p.toCharArray())
            h = (h * BASE + c) % MOD;
        patHashes.add(h);
    }
    
    long power = 1;
    for (int i = 0; i < m - 1; i++)
        power = (power * BASE) % MOD;
    
    long winHash = 0;
    for (int i = 0; i < m; i++)
        winHash = (winHash * BASE + text.charAt(i)) % MOD;
    
    for (int i = 0; i <= n - m; i++) {
        if (patHashes.contains(winHash)) {
            String sub = text.substring(i, i + m);
            if (patterns.contains(sub))
                result.add(i);
        }
        if (i < n - m) {
            winHash = (winHash - text.charAt(i) * power % MOD + MOD) % MOD;
            winHash = (winHash * BASE + text.charAt(i + m)) % MOD;
        }
    }
    return result;
}
```

### Complexity
- **Time:** O(n + m) average, O(nm) worst (many collisions)
- **Space:** O(1) for single pattern, O(k) for k patterns

---

## 3. Z-Algorithm

### Signal
- Find all occurrences of pattern in text
- Compute longest substring starting from each position that matches a prefix
- Simpler alternative to KMP for competitive programming

### Template (Java)

```java
int[] zFunction(String s) {
    int n = s.length();
    int[] z = new int[n];
    int l = 0, r = 0; // [l, r) is the rightmost Z-box
    
    for (int i = 1; i < n; i++) {
        if (i < r) {
            z[i] = Math.min(r - i, z[i - l]);
        }
        // Extend naively
        while (i + z[i] < n && s.charAt(z[i]) == s.charAt(i + z[i])) {
            z[i]++;
        }
        // Update Z-box
        if (i + z[i] > r) {
            l = i;
            r = i + z[i];
        }
    }
    return z;
}

// Pattern search using Z-Algorithm
List<Integer> zSearch(String text, String pattern) {
    String concat = pattern + "$" + text; // $ is sentinel (not in either string)
    int[] z = zFunction(concat);
    int m = pattern.length();
    
    List<Integer> result = new ArrayList<>();
    for (int i = m + 1; i < concat.length(); i++) {
        if (z[i] == m) {
            result.add(i - m - 1); // position in original text
        }
    }
    return result;
}
```

### Visualization

```
String: "aabxaab"
Z-array: [-, 1, 0, 0, 3, 1, 0]
          a  a  b  x  a  a  b

z[1]=1: "a" matches prefix "a"
z[4]=3: "aab" matches prefix "aab"
z[5]=1: "a" matches prefix "a"

Pattern search: pattern="aab", text="aabxaabxaab"
Concat: "aab$aabxaabxaab"
Z:      [-, 1, 0, 0, 3, 1, 0, 0, 3, 1, 0, 0, 3, 1, 0]
                     ^              ^              ^
                   z=3=m          z=3=m          z=3=m
Matches at text positions: 0, 4, 8
```

### Complexity
- **Time:** O(n + m)
- **Space:** O(n + m)

---

## 4. Longest Palindromic Substring

### Signal
- "Find longest palindromic substring"
- Expand around center for O(n^2) simplicity
- Manacher's for O(n) optimality

### Template (Java) — Expand Around Center

```java
String longestPalindrome(String s) {
    int n = s.length();
    int start = 0, maxLen = 1;
    
    for (int center = 0; center < n; center++) {
        // Odd-length palindromes
        int len1 = expand(s, center, center);
        // Even-length palindromes
        int len2 = expand(s, center, center + 1);
        
        int len = Math.max(len1, len2);
        if (len > maxLen) {
            maxLen = len;
            start = center - (len - 1) / 2;
        }
    }
    return s.substring(start, start + maxLen);
}

int expand(String s, int left, int right) {
    while (left >= 0 && right < s.length() && s.charAt(left) == s.charAt(right)) {
        left--;
        right++;
    }
    return right - left - 1; // length of palindrome
}
```

### Template (Java) — Manacher's Algorithm

```java
String manacher(String s) {
    // Transform: "abc" → "^#a#b#c#$"
    StringBuilder t = new StringBuilder("^#");
    for (char c : s.toCharArray()) {
        t.append(c).append('#');
    }
    t.append('$');
    
    int n = t.length();
    int[] p = new int[n]; // p[i] = radius of palindrome centered at i
    int center = 0, right = 0;
    
    for (int i = 1; i < n - 1; i++) {
        int mirror = 2 * center - i;
        
        if (i < right) {
            p[i] = Math.min(right - i, p[mirror]);
        }
        
        // Expand
        while (t.charAt(i + p[i] + 1) == t.charAt(i - p[i] - 1)) {
            p[i]++;
        }
        
        // Update center/right
        if (i + p[i] > right) {
            center = i;
            right = i + p[i];
        }
    }
    
    // Find max
    int maxLen = 0, maxCenter = 0;
    for (int i = 1; i < n - 1; i++) {
        if (p[i] > maxLen) {
            maxLen = p[i];
            maxCenter = i;
        }
    }
    
    int start = (maxCenter - maxLen) / 2; // map back to original
    return s.substring(start, start + maxLen);
}
```

### Visualization (Manacher's)

```
Original: "babad"
Transformed: "^#b#a#b#a#d#$"

Position:  0 1 2 3 4 5 6 7 8 9 10 11 12
Char:      ^ # b # a # b # a #  d  #  $
P[i]:      0 0 1 0 3 0 3 0 1 0  1  0  0
                   ↑       ↑
                 "aba"   "bab"  (both length 3)

P[4]=3 → palindrome of length 3 centered at 'a' → "bab"
P[6]=3 → palindrome of length 3 centered at 'b' → "aba"
```

### Complexity
- **Expand Around Center:** O(n^2) time, O(1) space
- **Manacher's:** O(n) time, O(n) space

---

## 5. Longest Palindromic Subsequence (DP)

### Signal
- "Find longest palindromic subsequence"
- Classic interval DP / LCS variant
- Key insight: LPS(s) = LCS(s, reverse(s))

### Template (Java)

```java
// Direct interval DP approach
int longestPalinSubseq(String s) {
    int n = s.length();
    int[][] dp = new int[n][n];
    
    // Base: single characters are palindromes of length 1
    for (int i = 0; i < n; i++) dp[i][i] = 1;
    
    // Fill diagonally (increasing length)
    for (int len = 2; len <= n; len++) {
        for (int i = 0; i <= n - len; i++) {
            int j = i + len - 1;
            if (s.charAt(i) == s.charAt(j)) {
                dp[i][j] = dp[i + 1][j - 1] + 2;
            } else {
                dp[i][j] = Math.max(dp[i + 1][j], dp[i][j - 1]);
            }
        }
    }
    return dp[0][n - 1];
}

// Space-optimized using LCS with reverse
int lpsViaLCS(String s) {
    String rev = new StringBuilder(s).reverse().toString();
    int n = s.length();
    int[] prev = new int[n + 1], curr = new int[n + 1];
    
    for (int i = 1; i <= n; i++) {
        for (int j = 1; j <= n; j++) {
            if (s.charAt(i - 1) == rev.charAt(j - 1))
                curr[j] = prev[j - 1] + 1;
            else
                curr[j] = Math.max(prev[j], curr[j - 1]);
        }
        int[] tmp = prev; prev = curr; curr = tmp;
        Arrays.fill(curr, 0);
    }
    return prev[n];
}
```

### Visualization

```
s = "bbbab"

dp[i][j] = LPS length of s[i..j]

    b  b  b  a  b
b  [1, 2, 3, 3, 4]
b  [0, 1, 2, 2, 3]
b  [0, 0, 1, 1, 3]
a  [0, 0, 0, 1, 1]
b  [0, 0, 0, 0, 1]

Answer: dp[0][4] = 4 → "bbbb"
```

### Complexity
- **Time:** O(n^2)
- **Space:** O(n^2) standard, O(n) with LCS optimization

---

## 6. Regular Expression Matching

### Signal
- Pattern with `.` (any single char) and `*` (zero or more of preceding)
- LeetCode 10: "isMatch(s, p)"

### Template (Java)

```java
boolean isMatch(String s, String p) {
    int m = s.length(), n = p.length();
    boolean[][] dp = new boolean[m + 1][n + 1];
    
    dp[0][0] = true;
    
    // Handle patterns like "a*b*c*" matching empty string
    for (int j = 2; j <= n; j += 2) {
        if (p.charAt(j - 1) == '*') {
            dp[0][j] = dp[0][j - 2];
        }
    }
    
    for (int i = 1; i <= m; i++) {
        for (int j = 1; j <= n; j++) {
            char sc = s.charAt(i - 1);
            char pc = p.charAt(j - 1);
            
            if (pc == '.' || pc == sc) {
                dp[i][j] = dp[i - 1][j - 1];
            } else if (pc == '*') {
                char prev = p.charAt(j - 2);
                // Zero occurrences of prev
                dp[i][j] = dp[i][j - 2];
                // One or more occurrences (if prev matches current char)
                if (prev == '.' || prev == sc) {
                    dp[i][j] = dp[i][j] || dp[i - 1][j];
                }
            }
        }
    }
    return dp[m][n];
}
```

### Visualization

```
s = "aab", p = "c*a*b"

dp[i][j]: does s[0..i-1] match p[0..j-1]?

      ""  c   *   a   *   b
""  [  T  F   T   F   T   F ]
a   [  F  F   F   T   T   F ]
a   [  F  F   F   F   T   F ]
b   [  F  F   F   F   F   T ]

"c*" matches "" (zero c's), "a*" matches "aa", "b" matches "b" → TRUE
```

### Complexity
- **Time:** O(m * n)
- **Space:** O(m * n), reducible to O(n)

---

## 7. Wildcard Matching

### Signal
- Pattern with `?` (any single char) and `*` (any sequence including empty)
- LeetCode 44
- Difference from regex: `*` is standalone (matches any sequence)

### Template (Java)

```java
boolean isMatch(String s, String p) {
    int m = s.length(), n = p.length();
    boolean[][] dp = new boolean[m + 1][n + 1];
    
    dp[0][0] = true;
    // Leading '*' can match empty
    for (int j = 1; j <= n; j++) {
        if (p.charAt(j - 1) == '*') dp[0][j] = dp[0][j - 1];
    }
    
    for (int i = 1; i <= m; i++) {
        for (int j = 1; j <= n; j++) {
            char pc = p.charAt(j - 1);
            if (pc == '?' || pc == s.charAt(i - 1)) {
                dp[i][j] = dp[i - 1][j - 1];
            } else if (pc == '*') {
                // '*' matches empty (dp[i][j-1]) or extends (dp[i-1][j])
                dp[i][j] = dp[i][j - 1] || dp[i - 1][j];
            }
        }
    }
    return dp[m][n];
}

// O(n) space optimization
boolean isMatchOptimized(String s, String p) {
    int m = s.length(), n = p.length();
    boolean[] prev = new boolean[n + 1];
    boolean[] curr = new boolean[n + 1];
    
    prev[0] = true;
    for (int j = 1; j <= n; j++)
        if (p.charAt(j - 1) == '*') prev[j] = prev[j - 1];
    
    for (int i = 1; i <= m; i++) {
        curr[0] = false;
        for (int j = 1; j <= n; j++) {
            char pc = p.charAt(j - 1);
            if (pc == '?' || pc == s.charAt(i - 1))
                curr[j] = prev[j - 1];
            else if (pc == '*')
                curr[j] = curr[j - 1] || prev[j];
            else
                curr[j] = false;
        }
        boolean[] tmp = prev; prev = curr; curr = tmp;
    }
    return prev[n];
}
```

### Complexity
- **Time:** O(m * n)
- **Space:** O(n) with optimization

---

## 8. String Hashing (Polynomial Rolling Hash)

### Signal
- O(1) substring equality comparison after O(n) preprocessing
- Detecting duplicate substrings
- Binary search on string properties (e.g., longest common substring)

### Template (Java)

```java
class StringHash {
    long[] hash, power;
    long MOD = 1_000_000_007, BASE = 31;
    
    StringHash(String s) {
        int n = s.length();
        hash = new long[n + 1];
        power = new long[n + 1];
        power[0] = 1;
        
        for (int i = 0; i < n; i++) {
            hash[i + 1] = (hash[i] * BASE + (s.charAt(i) - 'a' + 1)) % MOD;
            power[i + 1] = (power[i] * BASE) % MOD;
        }
    }
    
    // Get hash of s[l..r] (0-indexed, inclusive)
    long getHash(int l, int r) {
        long h = (hash[r + 1] - hash[l] * power[r - l + 1] % MOD + MOD * MOD) % MOD;
        return h;
    }
    
    // Check if s[l1..r1] == s[l2..r2] via hash
    boolean equal(int l1, int r1, int l2, int r2) {
        return getHash(l1, r1) == getHash(l2, r2);
    }
}

// Double hashing for safety
class DoubleHash {
    long[] h1, h2, p1, p2;
    long MOD1 = 1_000_000_007, MOD2 = 998_244_353;
    long BASE1 = 31, BASE2 = 37;
    
    DoubleHash(String s) {
        int n = s.length();
        h1 = new long[n + 1]; h2 = new long[n + 1];
        p1 = new long[n + 1]; p2 = new long[n + 1];
        p1[0] = p2[0] = 1;
        
        for (int i = 0; i < n; i++) {
            int c = s.charAt(i) - 'a' + 1;
            h1[i + 1] = (h1[i] * BASE1 + c) % MOD1;
            h2[i + 1] = (h2[i] * BASE2 + c) % MOD2;
            p1[i + 1] = p1[i] * BASE1 % MOD1;
            p2[i + 1] = p2[i] * BASE2 % MOD2;
        }
    }
    
    long[] getHash(int l, int r) {
        long v1 = (h1[r + 1] - h1[l] * p1[r - l + 1] % MOD1 + MOD1 * 2) % MOD1;
        long v2 = (h2[r + 1] - h2[l] * p2[r - l + 1] % MOD2 + MOD2 * 2) % MOD2;
        return new long[]{v1, v2};
    }
}
```

### Application: Longest Common Substring via Binary Search + Hashing

```java
int longestCommonSubstring(String a, String b) {
    int lo = 0, hi = Math.min(a.length(), b.length());
    
    while (lo < hi) {
        int mid = (lo + hi + 1) / 2;
        if (hasCommonSubstring(a, b, mid)) lo = mid;
        else hi = mid - 1;
    }
    return lo;
}

boolean hasCommonSubstring(String a, String b, int len) {
    StringHash ha = new StringHash(a);
    Set<Long> hashes = new HashSet<>();
    for (int i = 0; i + len - 1 < a.length(); i++)
        hashes.add(ha.getHash(i, i + len - 1));
    
    StringHash hb = new StringHash(b);
    for (int i = 0; i + len - 1 < b.length(); i++)
        if (hashes.contains(hb.getHash(i, i + len - 1)))
            return true;
    return false;
}
```

### Complexity
- **Preprocessing:** O(n)
- **Query:** O(1) per substring hash
- **Space:** O(n)

---

## 9. Suffix Array

### Signal
- Sorted array of all suffixes (by starting index)
- Applications: longest repeated substring, LCP array, string search
- Better space than suffix tree: O(n) vs O(n) but smaller constant

### Template (Java)

```java
// O(n log n) suffix array construction
int[] buildSuffixArray(String s) {
    int n = s.length();
    Integer[] order = new Integer[n];
    for (int i = 0; i < n; i++) order[i] = i;
    
    int[] rank = new int[n], tmp = new int[n];
    for (int i = 0; i < n; i++) rank[i] = s.charAt(i);
    
    for (int gap = 1; gap < n; gap <<= 1) {
        final int g = gap;
        final int[] r = rank;
        
        Comparator<Integer> cmp = (a, b) -> {
            if (r[a] != r[b]) return r[a] - r[b];
            int ra = a + g < n ? r[a + g] : -1;
            int rb = b + g < n ? r[b + g] : -1;
            return ra - rb;
        };
        
        Arrays.sort(order, cmp);
        
        tmp[order[0]] = 0;
        for (int i = 1; i < n; i++) {
            tmp[order[i]] = tmp[order[i - 1]] + (cmp.compare(order[i], order[i - 1]) != 0 ? 1 : 0);
        }
        System.arraycopy(tmp, 0, rank, 0, n);
    }
    
    int[] sa = new int[n];
    for (int i = 0; i < n; i++) sa[i] = order[i];
    return sa;
}

// LCP array via Kasai's algorithm — O(n)
int[] buildLCP(String s, int[] sa) {
    int n = s.length();
    int[] rank = new int[n], lcp = new int[n];
    
    for (int i = 0; i < n; i++) rank[sa[i]] = i;
    
    int h = 0;
    for (int i = 0; i < n; i++) {
        if (rank[i] > 0) {
            int j = sa[rank[i] - 1];
            while (i + h < n && j + h < n && s.charAt(i + h) == s.charAt(j + h))
                h++;
            lcp[rank[i]] = h;
            if (h > 0) h--;
        } else {
            h = 0;
        }
    }
    return lcp;
}

// Longest Repeated Substring
String longestRepeatedSubstring(String s) {
    int[] sa = buildSuffixArray(s);
    int[] lcp = buildLCP(s, sa);
    
    int maxLCP = 0, idx = 0;
    for (int i = 1; i < s.length(); i++) {
        if (lcp[i] > maxLCP) {
            maxLCP = lcp[i];
            idx = sa[i];
        }
    }
    return maxLCP > 0 ? s.substring(idx, idx + maxLCP) : "";
}
```

### Visualization

```
s = "banana$"

Suffixes sorted:
SA[0] = 6: "$"
SA[1] = 5: "a$"
SA[2] = 3: "ana$"
SA[3] = 1: "anana$"
SA[4] = 0: "banana$"
SA[5] = 4: "na$"
SA[6] = 2: "nana$"

LCP array (Kasai's):
LCP = [0, 0, 1, 3, 0, 0, 2]
              ↑   ↑       ↑
          a$/ana  ana/anana  na/nana

Longest repeated substring: "ana" (LCP max = 3)
```

### Complexity
- **Construction:** O(n log n) with sorting, O(n) with SA-IS
- **LCP (Kasai's):** O(n)
- **Space:** O(n)

---

## 10. Aho-Corasick

### Signal
- Search for MULTIPLE patterns simultaneously in text
- "Given a dictionary of words, find all occurrences in text"
- Like KMP but for multiple patterns — automaton on a trie

### Template (Java)

```java
class AhoCorasick {
    int[][] go;     // trie transitions
    int[] fail;     // failure links (like KMP's lps but on trie)
    int[] output;   // bitmask or count of patterns ending here
    int size;
    int ALPHA = 26;
    
    AhoCorasick(int maxNodes) {
        go = new int[maxNodes][ALPHA];
        fail = new int[maxNodes];
        output = new int[maxNodes];
        for (int[] row : go) Arrays.fill(row, -1);
        size = 1; // root = 0
    }
    
    // Insert pattern into trie
    void addPattern(String pattern, int patternId) {
        int cur = 0;
        for (char c : pattern.toCharArray()) {
            int ch = c - 'a';
            if (go[cur][ch] == -1) {
                go[cur][ch] = size++;
            }
            cur = go[cur][ch];
        }
        output[cur] |= (1 << patternId); // mark pattern end
    }
    
    // Build failure links via BFS
    void build() {
        Queue<Integer> queue = new LinkedList<>();
        
        // Initialize depth-1 nodes
        for (int c = 0; c < ALPHA; c++) {
            if (go[0][c] == -1) {
                go[0][c] = 0; // loop back to root
            } else {
                fail[go[0][c]] = 0;
                queue.add(go[0][c]);
            }
        }
        
        // BFS to set failure links
        while (!queue.isEmpty()) {
            int u = queue.poll();
            for (int c = 0; c < ALPHA; c++) {
                int v = go[u][c];
                if (v == -1) {
                    go[u][c] = go[fail[u]][c]; // shortcut
                } else {
                    fail[v] = go[fail[u]][c];
                    output[v] |= output[fail[v]]; // merge outputs
                    queue.add(v);
                }
            }
        }
    }
    
    // Search text for all pattern occurrences
    List<int[]> search(String text) {
        List<int[]> results = new ArrayList<>(); // [position, patternId]
        int cur = 0;
        
        for (int i = 0; i < text.length(); i++) {
            cur = go[cur][text.charAt(i) - 'a'];
            
            if (output[cur] != 0) {
                for (int j = 0; j < 30; j++) {
                    if ((output[cur] & (1 << j)) != 0) {
                        results.add(new int[]{i, j});
                    }
                }
            }
        }
        return results;
    }
}

// Usage
AhoCorasick ac = new AhoCorasick(100000);
String[] patterns = {"he", "she", "his", "hers"};
for (int i = 0; i < patterns.length; i++)
    ac.addPattern(patterns[i], i);
ac.build();
List<int[]> matches = ac.search("ahishers");
// Finds: "his" at 1, "she" at 3, "he" at 4, "hers" at 4
```

### Visualization

```
Patterns: {"he", "she", "his", "hers"}

Trie structure with failure links (→):
        root
       / | \
      h   s  (others→root)
     / \   \
    e   i    h
    |   |    |
    r   s    e
    |
    s

Failure links:
  "she"→"he" (suffix "he" exists)
  "he" →root
  "his"→root

Text: "ahishers"
State transitions: root→root→h→hi→his→sh→she→he→her→hers
Outputs found at each match point.
```

### Complexity
- **Build:** O(sum of pattern lengths * ALPHA) for goto + O(total) for BFS
- **Search:** O(n + z) where z = number of matches
- **Space:** O(sum of pattern lengths * ALPHA)

---

## 11. Shortest Palindrome (KMP Trick)

### Signal
- "Minimum characters to prepend to make string palindrome"
- LeetCode 214
- Key insight: find longest palindromic PREFIX, prepend reverse of suffix

### Template (Java)

```java
String shortestPalindrome(String s) {
    // Construct: s + "#" + reverse(s)
    // Find LPS of this → gives longest palindromic prefix of s
    String rev = new StringBuilder(s).reverse().toString();
    String concat = s + "#" + rev;
    
    int[] lps = buildLPS(concat); // reuse KMP's LPS function
    
    // lps[last] = length of longest palindromic prefix of s
    int palPrefixLen = lps[concat.length() - 1];
    
    // Prepend reverse of remaining suffix
    String toPrepend = rev.substring(0, s.length() - palPrefixLen);
    return toPrepend + s;
}
```

### Visualization

```
s = "aacecaaa"
rev = "aaacecaa"
concat = "aacecaaa#aaacecaa"

LPS of concat: [..., 7]  (last value = 7)
→ longest palindromic prefix = "aacecaa" (length 7)
→ prepend reverse of "a" (remaining) = "a"
→ result: "aaacecaaa"

Verification: "aaacecaaa" is a palindrome ✓
```

### Complexity
- **Time:** O(n)
- **Space:** O(n)

---

## 12. Repeated Substring Pattern

### Signal
- "Can string be constructed by repeating a substring?"
- LeetCode 459
- Two approaches: KMP-based and string doubling

### Template (Java) — KMP Approach

```java
// If n % (n - lps[n-1]) == 0, then s has a repeating pattern
// of length (n - lps[n-1])
boolean repeatedSubstringPattern(String s) {
    int n = s.length();
    int[] lps = buildLPS(s);
    
    int patternLen = n - lps[n - 1];
    // Must divide evenly AND not be the string itself
    return lps[n - 1] > 0 && n % patternLen == 0;
}
```

### Template (Java) — String Doubling Trick

```java
// If s+s contains s at a position OTHER than 0 and n, then s is repeated
boolean repeatedSubstringPattern(String s) {
    String doubled = s + s;
    // Remove first and last char to avoid trivial matches
    return doubled.substring(1, doubled.length() - 1).contains(s);
}
```

### Visualization

```
KMP approach:
s = "abcabcabc" (n=9)
LPS = [0, 0, 0, 1, 2, 3, 4, 5, 6]
lps[8] = 6
patternLen = 9 - 6 = 3
9 % 3 == 0 ✓ and lps[8] > 0 ✓ → repeated pattern "abc"

String doubling approach:
s = "abcabc"
s+s = "abcabcabcabc"
Remove first/last: "bcabcabcabc" → does NOT remove actual s
Search for "abcabc" in "bcabcabcab" → found at index 2 ✓

Why it works: if s = t^k, then s+s = t^(2k), and removing one char
from each end still leaves at least t^(2k-1) which contains t^k = s
at a non-trivial position.
```

### Complexity
- **KMP:** O(n) time, O(n) space
- **Doubling:** O(n) time (with KMP/Z for inner search), O(n) space

---

## Summary: When to Use What

```
┌─────────────────────────────────────────────────────────────┐
│ EXACT SINGLE PATTERN                                         │
│   → KMP (guaranteed O(n+m), deterministic)                  │
│   → Z-Algorithm (simpler to code, same complexity)          │
│   → Rabin-Karp (if avg-case OK, simpler rolling window)    │
├─────────────────────────────────────────────────────────────┤
│ EXACT MULTI-PATTERN                                          │
│   → Aho-Corasick (optimal: O(n + total_pattern_len + z))   │
│   → Rabin-Karp multi (simpler, good for same-length)       │
├─────────────────────────────────────────────────────────────┤
│ SUBSTRING EQUALITY / COMPARISON                              │
│   → String Hashing (O(1) per query after O(n) preprocess)  │
│   → Suffix Array + LCP (sorted suffix queries)             │
├─────────────────────────────────────────────────────────────┤
│ PALINDROME PROBLEMS                                          │
│   → Substring: Manacher O(n) or Expand O(n²)               │
│   → Subsequence: DP O(n²)                                  │
│   → Shortest palindrome: KMP trick O(n)                    │
├─────────────────────────────────────────────────────────────┤
│ PATTERN WITH WILDCARDS                                       │
│   → Regex (. and *): DP O(mn)                              │
│   → Wildcard (? and *): DP O(mn)                           │
├─────────────────────────────────────────────────────────────┤
│ REPEATED STRUCTURE                                           │
│   → Repeated substring: KMP trick O(n)                     │
│   → All repeated substrings: Suffix Array + LCP            │
└─────────────────────────────────────────────────────────────┘
```

---

## Common Pitfalls

1. **KMP**: Don't increment `i` on mismatch when `len != 0` in LPS construction
2. **Rabin-Karp**: Always verify on hash match; handle negative modulo (`+ MOD`)
3. **Manacher's**: Sentinel chars `^` and `$` prevent bounds checking
4. **Regex DP**: `*` refers to PRECEDING element — initialize `dp[0][j]` for `x*` patterns
5. **Wildcard DP**: `*` is standalone — different semantics from regex `*`
6. **String Hashing**: Use `(hash - char * power % MOD + MOD * MOD) % MOD` to avoid negatives
7. **Suffix Array**: Append sentinel `$` (lexicographically smallest) for correct ordering
8. **Aho-Corasick**: Don't forget to merge `output` along failure links
