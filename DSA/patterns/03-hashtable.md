# Hash Table - Pattern Guide

---

## Pattern Recognition Signals

| Signal | Pattern |
|--------|---------|
| Find pair summing to target | Complement Lookup |
| Top K frequent / sort by freq | Frequency + Bucket Sort |
| Group items by property | Group by Computed Key |
| Detect cycle in sequence | Hash as Visited Set |
| Longest consecutive sequence | Set + Start-of-Sequence |
| Subarray with exact sum | Prefix Sum + HashMap |
| Contains duplicate within K | Index Mapping |

---

## Pattern 1: Complement Lookup (Two Sum)

**When:** Find pair with property, one-pass matching.

### Template
```java
Map<Integer, Integer> map = new HashMap<>();
for (int i = 0; i < nums.length; i++) {
    int complement = target - nums[i];
    if (map.containsKey(complement)) return new int[]{map.get(complement), i};
    map.put(nums[i], i);
}
```

**Key Insight:** Store what you've SEEN, look up what you NEED.

### Extensions
| Problem | What to Store | What to Look Up |
|---------|--------------|-----------------|
| Two Sum | value → index | target - value |
| Two Sum (all pairs) | value → list of indices | target - value |
| 4Sum = target | pair sums → list of pairs | target - pairSum |
| Complement in array | set of values | k - value |

---

## Pattern 2: Frequency Counting + Bucket Sort

**When:** Top K frequent, sort by frequency, first unique.

### Template
```java
// Step 1: Count frequencies
Map<Integer, Integer> freq = new HashMap<>();
for (int num : nums) freq.merge(num, 1, Integer::sum);

// Step 2: Bucket sort (O(n) for Top K)
List<Integer>[] buckets = new List[n + 1];
for (var entry : freq.entrySet())
    buckets[entry.getValue()].add(entry.getKey());

// Step 3: Collect from highest frequency
List<Integer> result = new ArrayList<>();
for (int i = n; i >= 0 && result.size() < k; i--)
    if (buckets[i] != null) result.addAll(buckets[i]);
```

### Why Bucket Sort over Heap?
```
Heap approach: O(n log k) — good when k << n
Bucket sort:  O(n) — always linear, uses O(n) space

Buckets:
  freq=1: [5, 8]
  freq=2: [3, 7]
  freq=3: [1]      ← top 1 frequent = [1]
  freq=4: []
```

---

## Pattern 3: Group by Computed Key

**When:** Classify items sharing a property into groups.

### Template
```java
Map<String, List<String>> groups = new HashMap<>();
for (String word : words) {
    String key = computeKey(word);
    groups.computeIfAbsent(key, k -> new ArrayList<>()).add(word);
}
return new ArrayList<>(groups.values());
```

### Key Strategies

| Problem | Key Function |
|---------|-------------|
| Group Anagrams | `sorted(word)` or frequency encoding |
| Isomorphic Strings | Pattern: "egg"→"0.1.1", "add"→"0.1.1" |
| Word Pattern | Same pattern encoding |
| Shifted Strings | Difference encoding: "abc"→"1.1", "bcd"→"1.1" |

### Pattern Encoding
```java
// For isomorphic/word pattern:
String encode(String s) {
    Map<Character, Integer> map = new HashMap<>();
    StringBuilder sb = new StringBuilder();
    int id = 0;
    for (char c : s.toCharArray()) {
        map.putIfAbsent(c, id++);
        sb.append(map.get(c)).append('.');
    }
    return sb.toString();
}
// "egg" → "0.1.1."
// "add" → "0.1.1."  → same group!
```

---

## Pattern 4: Hash as Visited / Cycle Detection

**When:** Detect repetition in sequences, happy number, linked list cycle.

### Template
```java
Set<Integer> seen = new HashSet<>();
while (!seen.contains(x)) {
    seen.add(x);
    x = transform(x);
}
// x is the first repeated state (cycle entry)
```

### Happy Number Example
```
19 → 1² + 9² = 82
82 → 64 + 4 = 68
68 → 36 + 64 = 100
100 → 1 → happy!

2 → 4 → 16 → 37 → 58 → 89 → 145 → 42 → 20 → 4 (cycle!)
```

**Alternative:** Floyd's Tortoise/Hare for O(1) space.

---

## Pattern 5: Longest Consecutive Sequence

**When:** Find longest consecutive sequence in unsorted array. O(n).

### Template
```java
Set<Integer> numSet = new HashSet<>(Arrays.asList(nums));
int maxLen = 0;
for (int num : numSet) {
    if (!numSet.contains(num - 1)) {  // only start from sequence BEGINNING
        int length = 1;
        while (numSet.contains(num + length)) length++;
        maxLen = Math.max(maxLen, length);
    }
}
return maxLen;
```

### Key Insight
```
nums = [100, 4, 200, 1, 3, 2]
set = {100, 4, 200, 1, 3, 2}

Only start counting from elements that have NO predecessor:
  100: 100-1=99 not in set → start! count: 100 → length 1
  4: 4-1=3 in set → skip (not a start)
  200: 200-1=199 not in set → start! count: 200 → length 1
  1: 1-1=0 not in set → start! count: 1,2,3,4 → length 4 ✓
  3: skip (2 exists)
  2: skip (1 exists)
```

**Complexity:** O(n) — each element visited at most twice

---

## Pattern 6: Index Mapping (Window Duplicates)

**When:** Contains duplicate within distance K.

### Template
```java
Map<Integer, Integer> lastIndex = new HashMap<>();
for (int i = 0; i < nums.length; i++) {
    if (lastIndex.containsKey(nums[i]) && i - lastIndex.get(nums[i]) <= k)
        return true;
    lastIndex.put(nums[i], i);
}
return false;
```

### Variant: Sliding Window Set (alternative)
```java
Set<Integer> window = new HashSet<>();
for (int i = 0; i < nums.length; i++) {
    if (i > k) window.remove(nums[i - k - 1]);  // maintain window of size k
    if (!window.add(nums[i])) return true;       // duplicate in window
}
```

---

## Pattern 7: Design HashMap from Scratch

**When:** System design or implement hash table.

### Template
```java
class MyHashMap {
    private static final int SIZE = 1000;
    private List<int[]>[] buckets;  // separate chaining
    
    public MyHashMap() {
        buckets = new List[SIZE];
    }
    
    private int hash(int key) { return key % SIZE; }
    
    public void put(int key, int value) {
        int idx = hash(key);
        if (buckets[idx] == null) buckets[idx] = new ArrayList<>();
        for (int[] pair : buckets[idx]) {
            if (pair[0] == key) { pair[1] = value; return; }
        }
        buckets[idx].add(new int[]{key, value});
    }
    
    public int get(int key) {
        int idx = hash(key);
        if (buckets[idx] != null)
            for (int[] pair : buckets[idx])
                if (pair[0] == key) return pair[1];
        return -1;
    }
}
```

### Collision Resolution Strategies
```
1. Separate Chaining: each bucket → linked list/array of entries
2. Open Addressing: 
   - Linear probing: next slot
   - Quadratic probing: i² offset
   - Double hashing: second hash function
3. Robin Hood Hashing: steal from rich (short probe) to give to poor (long probe)
```

---

## Summary

```
HashMap Problem?
│
├─ Find complement/pair? ──────→ One-pass complement lookup
│
├─ Frequency analysis? ────────→ Counter + Bucket Sort
│
├─ Group by property? ─────────→ Computed key → Map<Key, List>
│
├─ Detect cycle/repetition? ──→ HashSet as visited
│
├─ Longest consecutive? ───────→ Set + start-of-sequence check
│
├─ Duplicates within window? ──→ Index mapping or window set
│
└─ Design hash structure? ─────→ Array + chaining + hash function
```
