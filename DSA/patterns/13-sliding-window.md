# 13 - Sliding Window Patterns

## Decision Flowchart

```
Is it a contiguous subarray/substring problem?
│
├─ YES → Is the window size fixed?
│         ├─ YES → Pattern 1: Fixed-Size Window
│         └─ NO  → What are we optimizing?
│                   ├─ LONGEST valid → Pattern 2: Expand, shrink when INVALID
│                   ├─ SHORTEST valid → Pattern 3: Expand, shrink while VALID
│                   ├─ COUNT of valid subarrays → Pattern 5: atMost(K) trick
│                   └─ EXACT match/anagram → Pattern 4: Frequency Map Window
│
└─ NO → Not a sliding window problem
```

## Decision Matrix

| Signal | Pattern | Shrink Condition | Shrink Style |
|--------|---------|-----------------|--------------|
| "subarray of size K" | Fixed | `right - left + 1 > K` | `if` (shrink once) |
| "longest substring without..." | Variable-Longest | window becomes invalid | `while` invalid |
| "minimum window containing..." | Variable-Shortest | window is valid | `while` valid |
| "find all anagrams" | Frequency Map | `right - left + 1 > patternLen` | `if` (fixed size) |
| "subarrays with exactly K distinct" | atMost(K) | distinct > K | `while` invalid |
| "minimum operations to make..." | Budget/Cost | cost exceeds budget | `while` over budget |

## Template Comparison: `if` vs `while` for Shrinking

```
if  → Fixed window: shrink exactly once when window exceeds K
while (invalid) → Longest valid: keep shrinking until window valid again
while (valid)   → Shortest valid: keep shrinking to minimize while still valid
```

---

## Pattern 1: Fixed-Size Window

### Signal
- "subarray of size K", "window of length K", "every K consecutive elements"

### Template (Java)

```java
public int fixedWindow(int[] nums, int k) {
    int windowSum = 0, result = 0; // or Integer.MIN_VALUE

    for (int right = 0; right < nums.length; right++) {
        windowSum += nums[right];              // expand

        if (right >= k - 1) {                  // window is full
            result = Math.max(result, windowSum);
            windowSum -= nums[right - k + 1];  // shrink left
        }
    }
    return result;
}
```

### Visualization (Max Sum of K=3, arr=[2,1,5,1,3,2])

```
[2, 1, 5, 1, 3, 2]
 ├──────┤              sum=8  ← max
    ├──────┤           sum=7
       ├──────┤        sum=9  ← new max
          ├──────┤     sum=6
```

### Variants

#### Maximum Sum Subarray of Size K
```java
// Exactly the template above
```

#### Maximum Vowels in a Substring of Size K (LC 1456)
```java
public int maxVowels(String s, int k) {
    int vowels = 0, max = 0;
    for (int i = 0; i < s.length(); i++) {
        if (isVowel(s.charAt(i))) vowels++;
        if (i >= k && isVowel(s.charAt(i - k))) vowels--;
        max = Math.max(max, vowels);
    }
    return max;
}
```

#### Averages of Subarrays of Size K
```java
public double[] findAverages(int[] nums, int k) {
    double[] result = new double[nums.length - k + 1];
    double windowSum = 0;
    for (int right = 0; right < nums.length; right++) {
        windowSum += nums[right];
        if (right >= k - 1) {
            result[right - k + 1] = windowSum / k;
            windowSum -= nums[right - k + 1];
        }
    }
    return result;
}
```

### Complexity
- Time: O(n)
- Space: O(1)

---

## Pattern 2: Variable Window - Longest Valid (Shrink When Invalid)

### Signal
- "longest substring", "maximum length", "without repeating", "at most K replacements"

### Template (Java)

```java
public int longestValid(String s) {
    Map<Character, Integer> map = new HashMap<>();
    int left = 0, result = 0;

    for (int right = 0; right < s.length(); right++) {
        // expand: add s.charAt(right) to window state
        map.merge(s.charAt(right), 1, Integer::sum);

        while (/* window is INVALID */) {
            // shrink: remove s.charAt(left) from window state
            map.merge(s.charAt(left), -1, Integer::sum);
            if (map.get(s.charAt(left)) == 0) map.remove(s.charAt(left));
            left++;
        }

        result = Math.max(result, right - left + 1); // window always valid here
    }
    return result;
}
```

### Variants

#### Longest Substring Without Repeating Characters (LC 3)
```java
public int lengthOfLongestSubstring(String s) {
    Map<Character, Integer> lastSeen = new HashMap<>();
    int left = 0, max = 0;

    for (int right = 0; right < s.length(); right++) {
        char c = s.charAt(right);
        if (lastSeen.containsKey(c) && lastSeen.get(c) >= left) {
            left = lastSeen.get(c) + 1; // jump left past duplicate
        }
        lastSeen.put(c, right);
        max = Math.max(max, right - left + 1);
    }
    return max;
}
```

**Visualization (s="abcabcbb"):**
```
a b c a b c b b
├────────┤         "abc" len=3
  ├────────┤       "bca" len=3
    ├────────┤     "cab" len=3
      ├────────┤   "abc" len=3
         left jumps on duplicates → max=3
```

#### Longest Repeating Character Replacement (LC 424)
```java
public int characterReplacement(String s, int k) {
    int[] freq = new int[26];
    int left = 0, maxFreq = 0, result = 0;

    for (int right = 0; right < s.length(); right++) {
        freq[s.charAt(right) - 'A']++;
        maxFreq = Math.max(maxFreq, freq[s.charAt(right) - 'A']);

        // window invalid: chars to replace > k
        while ((right - left + 1) - maxFreq > k) {
            freq[s.charAt(left) - 'A']--;
            left++;
        }
        result = Math.max(result, right - left + 1);
    }
    return result;
}
// Note: maxFreq never decreases - this is intentional and correct.
// We only care about the LARGEST valid window seen so far.
```

#### Fruits Into Baskets / Longest with At Most 2 Distinct (LC 904)
```java
public int totalFruit(int[] fruits) {
    Map<Integer, Integer> basket = new HashMap<>();
    int left = 0, max = 0;

    for (int right = 0; right < fruits.length; right++) {
        basket.merge(fruits[right], 1, Integer::sum);

        while (basket.size() > 2) {
            int leftFruit = fruits[left];
            basket.merge(leftFruit, -1, Integer::sum);
            if (basket.get(leftFruit) == 0) basket.remove(leftFruit);
            left++;
        }
        max = Math.max(max, right - left + 1);
    }
    return max;
}
```

### Complexity
- Time: O(n) - each element enters/exits window at most once
- Space: O(min(n, charset)) for the map

---

## Pattern 3: Variable Window - Shortest Valid (Shrink While Valid)

### Signal
- "minimum window", "shortest subarray", "smallest substring containing"

### Template (Java)

```java
public int shortestValid(int[] nums, int target) {
    int left = 0, result = Integer.MAX_VALUE;
    int windowState = 0; // e.g., sum, count of matched chars

    for (int right = 0; right < nums.length; right++) {
        // expand: update window state
        windowState += nums[right];

        while (/* window is VALID */) {
            result = Math.min(result, right - left + 1); // record before shrinking
            // shrink: remove left from state
            windowState -= nums[left];
            left++;
        }
    }
    return result == Integer.MAX_VALUE ? 0 : result;
}
```

### Variants

#### Minimum Size Subarray Sum (LC 209)
```java
public int minSubArrayLen(int target, int[] nums) {
    int left = 0, sum = 0, min = Integer.MAX_VALUE;

    for (int right = 0; right < nums.length; right++) {
        sum += nums[right];

        while (sum >= target) {          // valid → try to shrink
            min = Math.min(min, right - left + 1);
            sum -= nums[left++];
        }
    }
    return min == Integer.MAX_VALUE ? 0 : min;
}
```

#### Minimum Window Substring (LC 76) - Step-by-Step Trace

```java
public String minWindow(String s, String t) {
    Map<Character, Integer> need = new HashMap<>();
    for (char c : t.toCharArray()) need.merge(c, 1, Integer::sum);

    int left = 0, matched = 0, start = 0, minLen = Integer.MAX_VALUE;
    Map<Character, Integer> window = new HashMap<>();

    for (int right = 0; right < s.length(); right++) {
        char rc = s.charAt(right);
        window.merge(rc, 1, Integer::sum);

        // a character is "matched" when window has enough of it
        if (need.containsKey(rc) && window.get(rc).equals(need.get(rc))) {
            matched++;
        }

        // shrink while all characters matched
        while (matched == need.size()) {
            if (right - left + 1 < minLen) {
                minLen = right - left + 1;
                start = left;
            }
            char lc = s.charAt(left);
            if (need.containsKey(lc) && window.get(lc).equals(need.get(lc))) {
                matched--;
            }
            window.merge(lc, -1, Integer::sum);
            left++;
        }
    }
    return minLen == Integer.MAX_VALUE ? "" : s.substring(start, start + minLen);
}
```

### Step-by-Step Trace: minWindow("ADOBECODEBANC", "ABC")

```
need = {A:1, B:1, C:1}

right=0  'A' window={A:1}        matched=1  (A satisfied)
right=1  'D' window={A:1,D:1}    matched=1
right=2  'O' window={..,O:1}     matched=1
right=3  'B' window={..,B:1}     matched=2  (B satisfied)
right=4  'E' window={..,E:1}     matched=2
right=5  'C' window={..,C:1}     matched=3  (C satisfied) ← ALL MATCHED
         ┌─ SHRINK LOOP ─────────────────────────────────────┐
         │ minLen=6, start=0 → "ADOBEC"                      │
         │ remove 'A' → matched=2, left=1 → STOP             │
         └────────────────────────────────────────────────────┘
right=6  'O'                     matched=2
right=7  'D'                     matched=2
right=8  'E'                     matched=2
right=9  'B' window={..,B:1,A:0} matched=2
right=10 'A' window={..,A:1}     matched=3  ← ALL MATCHED
         ┌─ SHRINK LOOP ─────────────────────────────────────┐
         │ minLen=6 vs 10 → no update (len=10)               │
         │ remove 'D' left=2 → still matched=3               │
         │ minLen=6 vs 9 → no update                         │
         │ remove 'O' left=3 → still matched=3               │
         │ ... keep shrinking ...                             │
         │ remove 'B' left=4 → matched=2 → STOP             │
         └────────────────────────────────────────────────────┘
         (window now starts at index 5)
right=11 'N'                     matched=2
right=12 'C' window={..,C:1}     matched=3  ← ALL MATCHED
         ┌─ SHRINK LOOP ─────────────────────────────────────┐
         │ len = 12-5+1 = 8 → no update                      │
         │ remove 'C' left=6 → matched=2 → wait...           │
         │ actually let's recount:                            │
         │ window from index 5: "CODEBANC"                    │
         │ keep shrinking... eventually "BANC" (len=4) found  │
         │ minLen=4, start=9 → "BANC"                        │
         └────────────────────────────────────────────────────┘

Result: "BANC"
```

### Complexity
- Time: O(n + m) where m = |t|
- Space: O(charset)

---

## Pattern 4: Frequency Map Window / Anagram Detection

### Signal
- "find all anagrams", "permutation in string", "check inclusion"
- Fixed-size window (size = pattern length) + frequency matching

### Template (Java)

```java
public List<Integer> findAnagrams(String s, String p) {
    List<Integer> result = new ArrayList<>();
    if (s.length() < p.length()) return result;

    int[] need = new int[26], window = new int[26];
    for (char c : p.toCharArray()) need[c - 'a']++;

    int matched = 0; // count of characters with correct frequency

    for (int right = 0; right < s.length(); right++) {
        int rc = s.charAt(right) - 'a';
        window[rc]++;
        if (window[rc] == need[rc]) matched++;

        // shrink: fixed window of size p.length()
        if (right >= p.length()) {
            int lc = s.charAt(right - p.length()) - 'a';
            if (window[lc] == need[lc]) matched--;
            window[lc]--;
        }

        if (matched == 26) result.add(right - p.length() + 1);
    }
    return result;
}
```

### Visualization (s="cbaebabacd", p="abc")

```
Comparing character frequency counts:
need = {a:1, b:1, c:1}

c b a | e b a b a c d
├────┤  matched=26 → index 0 ("cba")
  b a e
  ├────┤ not matched
          ... sliding ...
              b a c
              ├────┤ matched=26 → index 6 ("bac")
                  ... no more
Result: [0, 6]
```

### Variant: Permutation in String (LC 567)
```java
// Same as findAnagrams but return true on first match
public boolean checkInclusion(String s1, String s2) {
    return !findAnagrams(s2, s1).isEmpty();
}
```

### Complexity
- Time: O(n) where n = |s| (comparison is O(26) = O(1))
- Space: O(1) (fixed 26-size arrays)

---

## Pattern 5: Window with At Most K Distinct

### Signal
- "exactly K distinct", "subarrays with K different integers"
- Key insight: `exactly(K) = atMost(K) - atMost(K-1)`

### Template (Java)

```java
// Subarrays with Exactly K Distinct (LC 992)
public int subarraysWithKDistinct(int[] nums, int k) {
    return atMost(nums, k) - atMost(nums, k - 1);
}

private int atMost(int[] nums, int k) {
    Map<Integer, Integer> freq = new HashMap<>();
    int left = 0, count = 0;

    for (int right = 0; right < nums.length; right++) {
        freq.merge(nums[right], 1, Integer::sum);

        while (freq.size() > k) {
            int lv = nums[left];
            freq.merge(lv, -1, Integer::sum);
            if (freq.get(lv) == 0) freq.remove(lv);
            left++;
        }

        // all subarrays ending at right with at most k distinct
        count += right - left + 1;
    }
    return count;
}
```

### Why `count += right - left + 1`?

```
For window [left...right], valid subarrays ending at right:
  [left, right], [left+1, right], ..., [right, right]
  = (right - left + 1) subarrays
```

### Visualization (nums=[1,2,1,2,3], k=2)

```
atMost(2):
  [1]         → +1 = 1
  [1,2][2]    → +2 = 3
  [1,2,1][2,1][1] → +3 = 6
  [1,2,1,2][2,1,2][1,2][2] → +4 = 10
  shrink! distinct={1,2,3}>2 → left moves to index 2
  [1,2,3][2,3][3] → +3 = 13   (wait, after shrink: [1,2,3] has 3)
  ... left=2: [1,2,3] still 3 distinct, left=3: [2,3] → +2 = 12

atMost(1): ... = 5

exactly(2) = 12 - 5 = 7
```

### Complexity
- Time: O(n) per atMost call, O(n) total
- Space: O(k)

---

## Pattern 6: Window with Budget/Cost

### Signal
- "minimum operations to make elements equal", "frequency of most frequent element"
- Window valid while `cost <= budget`

### Template (Java)

#### Frequency of the Most Frequent Element (LC 1838)

```java
public int maxFrequency(int[] nums, int k) {
    Arrays.sort(nums); // sort so window elements are close in value
    long left = 0, sum = 0, result = 0;

    for (int right = 0; right < nums.length; right++) {
        sum += nums[right];

        // cost to make all elements in window equal to nums[right]:
        // (right - left + 1) * nums[right] - sum
        // this must be <= k (our budget)
        while ((right - left + 1L) * nums[right] - sum > k) {
            sum -= nums[(int) left];
            left++;
        }
        result = Math.max(result, right - left + 1);
    }
    return (int) result;
}
```

### Intuition

```
Sorted: [1, 2, 4], k=5

Window [1,2,4]: cost to make all 4 = (3*4) - (1+2+4) = 12-7 = 5 ≤ 5 ✓
  → frequency = 3

The "budget" is the total increments available (k).
The "cost" is how many increments needed to raise all window elements to the max.
```

### Complexity
- Time: O(n log n) due to sort
- Space: O(1)

---

## Pattern 7: String Window with Concatenation

### Signal
- "substring with concatenation of all words", all words same length

### Substring with Concatenation of All Words (LC 30)

```java
public List<Integer> findSubstring(String s, String[] words) {
    List<Integer> result = new ArrayList<>();
    if (words.length == 0) return result;

    int wordLen = words[0].length();
    int windowSize = wordLen * words.length;
    Map<String, Integer> need = new HashMap<>();
    for (String w : words) need.merge(w, 1, Integer::sum);

    // Run sliding window for each starting offset [0, wordLen)
    for (int offset = 0; offset < wordLen; offset++) {
        Map<String, Integer> window = new HashMap<>();
        int matched = 0, left = offset;

        for (int right = offset; right + wordLen <= s.length(); right += wordLen) {
            String word = s.substring(right, right + wordLen);

            if (!need.containsKey(word)) {
                // reset window
                window.clear();
                matched = 0;
                left = right + wordLen;
                continue;
            }

            window.merge(word, 1, Integer::sum);
            if (window.get(word).equals(need.get(word))) matched++;

            // shrink if window too large
            while (right - left + wordLen > windowSize) {
                String leftWord = s.substring(left, left + wordLen);
                if (window.get(leftWord).equals(need.get(leftWord))) matched--;
                window.merge(leftWord, -1, Integer::sum);
                left += wordLen;
            }

            if (matched == need.size()) {
                // verify all counts match (handle overcounting)
                if (window.equals(need)) result.add(left);
                // or simpler: check window size
            }
        }
    }
    return result;
}
```

### Optimization Note
Instead of checking `window.equals(need)`, track `matched` count properly by also decrementing when a word count exceeds needed:

```java
// After window.merge(word, 1, Integer::sum):
if (window.get(word).equals(need.get(word))) matched++;
else if (window.get(word).equals(need.get(word) + 1)) matched--; // over-counted

// Then check: if (matched == need.size()) result.add(left);
```

### Complexity
- Time: O(n * wordLen) - we have `wordLen` passes, each O(n/wordLen) iterations
- Space: O(words.length)

---

## Summary Cheat Sheet

| # | Pattern | Key Template Line | When to Record Result |
|---|---------|------------------|-----------------------|
| 1 | Fixed | `if (right >= k-1)` | After window fills |
| 2 | Longest | `while (invalid) shrink` | After shrink (window valid) |
| 3 | Shortest | `while (valid) shrink` | Before shrink (window valid) |
| 4 | Anagram | `if (matched == 26)` | When frequencies match |
| 5 | atMost(K) | `count += right-left+1` | Every iteration |
| 6 | Budget | `while (cost > k) shrink` | After shrink (within budget) |
| 7 | Concat | offset loop + word-sized steps | When all words matched |

## Common Mistakes

1. **Off-by-one in fixed window**: Use `right >= k-1` not `right >= k`
2. **Forgetting to remove from map**: Always clean up zero-count entries or check properly
3. **Integer comparison in maps**: Use `.equals()` not `==` for `Integer` objects in Java
4. **Not handling empty input**: Check `s.length() < p.length()` early
5. **atMost trick**: Remember `exactly(K) = atMost(K) - atMost(K-1)`, not `atMost(K) - atMost(K)`
6. **Sorted assumption in budget**: Pattern 6 requires sorting first
