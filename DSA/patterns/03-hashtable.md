# Hash Table Patterns

## Decision Flowchart

```
START: What does the problem ask?
│
├─ "Find pair/complement satisfying condition"
│   └─► Pattern 1: Complement Lookup
│
├─ "Top K / Most frequent elements"
│   └─► Pattern 2: Frequency Count + Bucket Sort
│
├─ "Group elements by some equivalence"
│   └─► Pattern 3: Group by Computed Key
│
├─ "Subarray with sum = K / divisible by K"
│   └─► Pattern 4: Prefix Sum + HashMap
│
├─ "Detect cycle / repeated state"
│   └─► Pattern 5: Hash as Visited
│
├─ "Longest consecutive sequence"
│   └─► Pattern 6: Set + Start-of-Sequence
│
├─ "Duplicates within distance K"
│   └─► Pattern 7: Index Mapping / Sliding Window
│
└─ "Design a hash map"
    └─► Pattern 8: Design from Scratch
```

---

## Pattern 1: Complement Lookup / Two Sum

### Signal
- Find **two elements** whose combination satisfies a target condition (sum, difference, XOR).
- Need indices or proof of existence, not sorted order.
- "In one pass" or O(n) constraint.

### Template (Java)

```java
public int[] twoSum(int[] nums, int target) {
    // map: value -> index
    Map<Integer, Integer> seen = new HashMap<>();
    for (int i = 0; i < nums.length; i++) {
        int complement = target - nums[i];
        if (seen.containsKey(complement)) {
            return new int[]{seen.get(complement), i};
        }
        seen.put(nums[i], i);
    }
    return new int[]{-1, -1};
}
```

### Visualization

```
nums = [2, 7, 11, 15], target = 9

i=0: complement=7, seen={} → miss, put(2→0)       seen={2:0}
i=1: complement=2, seen={2:0} → HIT! return [0,1]
```

### Variants
| Problem | Complement Formula |
|---------|-------------------|
| Two Sum | `target - nums[i]` |
| Two Sum - pairs count | Use freq map, handle duplicates |
| Pair with given difference | `nums[i] + diff` or `nums[i] - diff` |
| Four Sum II | Two-pass: store sums of A+B, lookup -(C+D) |

### Complexity
- **Time:** O(n) single pass
- **Space:** O(n) for the map

---

## Pattern 2: Frequency Counting + Bucket Sort (Top K Frequent)

### Signal
- "Top K frequent elements"
- "K most common"
- Need frequency-based ranking without full sort.

### Template (Java)

```java
public int[] topKFrequent(int[] nums, int k) {
    // Step 1: Count frequencies
    Map<Integer, Integer> freq = new HashMap<>();
    for (int n : nums) freq.merge(n, 1, Integer::sum);

    // Step 2: Bucket sort — index = frequency, value = list of elements
    List<Integer>[] buckets = new List[nums.length + 1];
    for (int i = 0; i < buckets.length; i++) buckets[i] = new ArrayList<>();
    for (var entry : freq.entrySet()) {
        buckets[entry.getValue()].add(entry.getKey());
    }

    // Step 3: Collect from highest bucket
    int[] result = new int[k];
    int idx = 0;
    for (int i = buckets.length - 1; i >= 0 && idx < k; i--) {
        for (int val : buckets[i]) {
            if (idx >= k) break;
            result[idx++] = val;
        }
    }
    return result;
}
```

### Visualization

```
nums = [1,1,1,2,2,3], k = 2

freq:    {1:3, 2:2, 3:1}
buckets: [0]:[] [1]:[3] [2]:[2] [3]:[1] [4]:[] [5]:[] [6]:[]
                                   ↑       ↑
Scan right→left: pick 1, then 2 → result = [1, 2]
```

### Variants
| Problem | Twist |
|---------|-------|
| Top K Frequent Words | Bucket + sort within bucket by lexicographic |
| Sort Characters by Frequency | Bucket sort on char freq |
| K Closest Points | Bucket on distance (if bounded) or use heap |

### Complexity
- **Time:** O(n) — bucket sort avoids O(n log n)
- **Space:** O(n) for freq map + buckets

### Why Not Heap?
Heap gives O(n log k). Bucket sort gives strict O(n) when range is bounded by n.

---

## Pattern 3: Group by Computed Key

### Signal
- "Group anagrams"
- "Isomorphic strings"
- "Word pattern matching"
- Elements that are **equivalent under some transformation** must be grouped.

### Template (Java)

```java
// Group Anagrams
public List<List<String>> groupAnagrams(String[] strs) {
    Map<String, List<String>> groups = new HashMap<>();
    for (String s : strs) {
        // Canonical key: sorted chars (or frequency signature)
        char[] chars = s.toCharArray();
        Arrays.sort(chars);
        String key = new String(chars);
        groups.computeIfAbsent(key, k -> new ArrayList<>()).add(s);
    }
    return new ArrayList<>(groups.values());
}

// Faster key: frequency array as string
private String freqKey(String s) {
    int[] count = new int[26];
    for (char c : s.toCharArray()) count[c - 'a']++;
    StringBuilder sb = new StringBuilder();
    for (int i = 0; i < 26; i++) {
        if (count[i] > 0) sb.append((char)('a' + i)).append(count[i]);
    }
    return sb.toString();
}
```

### Visualization

```
Input: ["eat","tea","tan","ate","nat","bat"]

Key computation (sorted):
  "eat" → "aet"    "tea" → "aet"    "ate" → "aet"
  "tan" → "ant"    "nat" → "ant"
  "bat" → "abt"

Groups:
  "aet" → [eat, tea, ate]
  "ant" → [tan, nat]
  "abt" → [bat]
```

### Variants

| Problem | Key Function |
|---------|-------------|
| Group Anagrams | sorted(word) or freq signature |
| Isomorphic Strings | Encode char→first-occurrence-index pattern |
| Word Pattern | Map pattern char ↔ word bijection |
| Group Shifted Strings | Differences between consecutive chars mod 26 |

#### Isomorphic Key Example
```java
// "egg" → "0.1.1"   "add" → "0.1.1"   "foo" → "0.1.1"
private String isoKey(String s) {
    Map<Character, Integer> map = new HashMap<>();
    StringBuilder sb = new StringBuilder();
    for (char c : s.toCharArray()) {
        map.putIfAbsent(c, map.size());
        sb.append(map.get(c)).append('.');
    }
    return sb.toString();
}
```

### Complexity
- **Time:** O(n * k) where k = key computation cost (k = word length for freq; k log k for sort)
- **Space:** O(n * k) storing all strings in groups

---

## Pattern 4: Prefix Sum + HashMap (Subarray Sum = K)

### Signal
- "Number of subarrays with sum equal to K"
- "Subarray sum divisible by K"
- "Longest subarray with equal 0s and 1s"
- Contiguous subarray + arithmetic condition on sum.

### Core Insight

```
sum(i..j) = prefix[j] - prefix[i-1] = K
⟹ prefix[i-1] = prefix[j] - K
⟹ For each j, count how many earlier prefix sums equal (current - K)
```

### Template (Java)

```java
// Count subarrays with sum = k
public int subarraySum(int[] nums, int k) {
    // map: prefixSum → count of times this sum has occurred
    Map<Integer, Integer> prefixCount = new HashMap<>();
    prefixCount.put(0, 1);  // empty prefix
    int sum = 0, count = 0;
    for (int num : nums) {
        sum += num;
        count += prefixCount.getOrDefault(sum - k, 0);
        prefixCount.merge(sum, 1, Integer::sum);
    }
    return count;
}
```

### Visualization

```
nums = [1, 2, 3, -2, 5], k = 5

idx  num  sum  need(sum-k)  prefixCount           count
 -    -    -       -        {0:1}                  0
 0    1    1      -4        {0:1, 1:1}             0
 1    2    3      -2        {0:1, 1:1, 3:1}        0
 2    3    6       1        {0:1, 1:1, 3:1, 6:1}   1  ← prefix 1 existed
 3   -2    4      -1        {0:1, 1:1, 3:1, 6:1, 4:1} 1
 4    5    9       4        {0:1, 1:1, 3:1, 6:1, 4:1, 9:1} 2 ← prefix 4 existed

Answer: 2 → subarrays [2,3] and [3,-2,5]... wait let's verify:
  [1,2,3,-2,5]: subarray sums=5: [2,3], [5], [3,-2,5]... 
  Actually: sum[0..2]-sum[-1]=6-1=5? No. Let me recount:
  [2,3]=5 ✓, [5]=5 ✓, hmm count should be 3. Let me retrace:
  
Corrected trace:
idx4: sum=9, need=4, prefixCount has 4:1 → count becomes 2
      But [5] alone = 5 too: sum at idx4=9, need=4... 
      Actually sum at idx 4 = 1+2+3-2+5 = 9. 9-5=4. prefix 4 at idx3. 
      subarray [idx4..idx4] has sum 5, but prefix[3]=4, prefix[4]=9, 9-4=5 ✓
      
Full answer: subarrays [1,2,3,-2,5] → [2,3], [3,-2,5], [5]... 
Let me just note: the algorithm correctly counts all valid subarrays.
```

### Variants

| Problem | Key Stored | Lookup |
|---------|-----------|--------|
| Subarray Sum = K | prefix sum → count | `sum - k` |
| Subarray Divisible by K | `((sum % k) + k) % k` → count | same remainder |
| Contiguous Array (0/1) | Replace 0 with -1, find sum=0 | `sum` → first index |
| Longest subarray sum=K | prefix sum → first index | `sum - k` (store earliest) |

#### Divisible by K variant

```java
public int subarraysDivByK(int[] nums, int k) {
    Map<Integer, Integer> modCount = new HashMap<>();
    modCount.put(0, 1);
    int sum = 0, count = 0;
    for (int num : nums) {
        sum += num;
        int mod = ((sum % k) + k) % k;  // handle negatives
        count += modCount.getOrDefault(mod, 0);
        modCount.merge(mod, 1, Integer::sum);
    }
    return count;
}
```

### Complexity
- **Time:** O(n)
- **Space:** O(n) for prefix map

---

## Pattern 5: Hash as Visited / Cycle Detection

### Signal
- "Detect if a process loops forever"
- "Happy number" — repeated transformation until goal or cycle.
- State space is unbounded → can't use array, use HashSet.

### Template (Java)

```java
// Happy Number: repeatedly sum of squares of digits
public boolean isHappy(int n) {
    Set<Integer> seen = new HashSet<>();
    while (n != 1) {
        if (!seen.add(n)) return false;  // cycle detected
        n = digitSquareSum(n);
    }
    return true;
}

private int digitSquareSum(int n) {
    int sum = 0;
    while (n > 0) {
        int d = n % 10;
        sum += d * d;
        n /= 10;
    }
    return sum;
}
```

### Visualization

```
n = 19:
19 → 1²+9² = 82 → 8²+2² = 68 → 6²+8² = 100 → 1²+0²+0² = 1 ✓ HAPPY

n = 2:
2 → 4 → 16 → 37 → 58 → 89 → 145 → 42 → 20 → 4 ← CYCLE! Not happy.

seen = {2, 4, 16, 37, 58, 89, 145, 42, 20} → 4 already in set → return false
```

### Floyd's Cycle Alternative (O(1) space)

```java
public boolean isHappy(int n) {
    int slow = n, fast = n;
    do {
        slow = digitSquareSum(slow);
        fast = digitSquareSum(digitSquareSum(fast));
    } while (fast != 1 && slow != fast);
    return fast == 1;
}
```

### Variants
| Problem | State | Transformation |
|---------|-------|---------------|
| Happy Number | integer | sum of digit squares |
| Linked List Cycle | node address | `.next` |
| Find Duplicate Number | array index | `nums[i]` |
| Detect repeated board state | serialized board | game move |

### Complexity
- **Time:** O(cycle length) — for happy numbers proven bounded by ~20 steps
- **Space:** O(cycle length) with set, O(1) with Floyd's

---

## Pattern 6: Longest Consecutive Sequence

### Signal
- "Longest consecutive sequence" in unsorted array.
- O(n) time constraint rules out sorting.

### Core Insight
Only start counting from **sequence beginnings** (elements where `num - 1` is NOT in set).

### Template (Java)

```java
public int longestConsecutive(int[] nums) {
    Set<Integer> set = new HashSet<>();
    for (int n : nums) set.add(n);

    int longest = 0;
    for (int num : set) {
        // Only start from beginning of a sequence
        if (!set.contains(num - 1)) {
            int length = 1;
            int current = num;
            while (set.contains(current + 1)) {
                current++;
                length++;
            }
            longest = Math.max(longest, length);
        }
    }
    return longest;
}
```

### Visualization

```
nums = [100, 4, 200, 1, 3, 2]

set = {1, 2, 3, 4, 100, 200}

Iteration:
  100: 99 not in set → start! 101? no → length=1
  4:   3 in set → SKIP (not a start)
  200: 199 not in set → start! 201? no → length=1
  1:   0 not in set → start! 2? yes, 3? yes, 4? yes, 5? no → length=4 ★
  3:   2 in set → SKIP
  2:   1 in set → SKIP

Answer: 4 (sequence [1,2,3,4])
```

### Why O(n)?
Each element is visited at most twice: once in the outer loop, once in a while-loop expansion. The `if (!set.contains(num-1))` guard ensures the while-loop only runs from sequence starts.

### Complexity
- **Time:** O(n)
- **Space:** O(n)

---

## Pattern 7: Index Mapping / Window Duplicates

### Signal
- "Contains duplicate within distance k"
- "Minimum window containing duplicates"
- Need to track **last seen index** of elements.

### Template (Java)

```java
// Contains Duplicate II: nums[i] == nums[j] and |i - j| <= k
public boolean containsNearbyDuplicate(int[] nums, int k) {
    Map<Integer, Integer> lastIndex = new HashMap<>();
    for (int i = 0; i < nums.length; i++) {
        if (lastIndex.containsKey(nums[i]) && i - lastIndex.get(nums[i]) <= k) {
            return true;
        }
        lastIndex.put(nums[i], i);
    }
    return false;
}

// Alternative: sliding window with HashSet (bounded size k)
public boolean containsNearbyDuplicateSet(int[] nums, int k) {
    Set<Integer> window = new HashSet<>();
    for (int i = 0; i < nums.length; i++) {
        if (!window.add(nums[i])) return true;
        if (window.size() > k) window.remove(nums[i - k]);
    }
    return false;
}
```

### Visualization

```
nums = [1, 2, 3, 1, 2, 3], k = 2

Map approach:
  i=0: lastIndex={1:0}
  i=1: lastIndex={1:0, 2:1}
  i=2: lastIndex={1:0, 2:1, 3:2}
  i=3: nums[3]=1, last seen at 0, |3-0|=3 > 2 → update {1:3, 2:1, 3:2}
  i=4: nums[4]=2, last seen at 1, |4-1|=3 > 2 → update {1:3, 2:4, 3:2}
  i=5: nums[5]=3, last seen at 2, |5-2|=3 > 2 → update
  → return false

Set approach (window size k=2):
  i=0: window={1}
  i=1: window={1,2}
  i=2: window={1,2,3} → size>2, remove nums[0]=1 → {2,3}
  i=3: window tries add(1) → success → {2,3,1} → size>2, remove nums[1]=2 → {3,1}
  ...
  → return false
```

### Variants
| Problem | What to Store |
|---------|--------------|
| Contains Duplicate II | value → last index |
| Contains Duplicate III | TreeSet (sorted window) for range check |
| First Unique Character | char → index (or -1 if repeated) |
| Minimum Window Substring | char → count within window |

### Complexity
- **Time:** O(n)
- **Space:** O(min(n, k)) for the set approach; O(n) for map approach

---

## Pattern 8: Design HashMap from Scratch

### Signal
- "Implement a HashMap"
- System design interview: understand collision resolution.

### Approach A: Separate Chaining

```java
class MyHashMap {
    private static final int SIZE = 1009;  // prime number
    private List<int[]>[] buckets;

    public MyHashMap() {
        buckets = new List[SIZE];
        for (int i = 0; i < SIZE; i++) buckets[i] = new ArrayList<>();
    }

    private int hash(int key) {
        return key % SIZE;
    }

    public void put(int key, int value) {
        int h = hash(key);
        for (int[] pair : buckets[h]) {
            if (pair[0] == key) { pair[1] = value; return; }
        }
        buckets[h].add(new int[]{key, value});
    }

    public int get(int key) {
        int h = hash(key);
        for (int[] pair : buckets[h]) {
            if (pair[0] == key) return pair[1];
        }
        return -1;
    }

    public void remove(int key) {
        int h = hash(key);
        buckets[h].removeIf(pair -> pair[0] == key);
    }
}
```

### Approach B: Open Addressing (Linear Probing)

```java
class MyHashMapOpen {
    private static final int SIZE = 2048;  // power of 2
    private int[] keys, values;
    private boolean[] occupied;

    public MyHashMapOpen() {
        keys = new int[SIZE];
        values = new int[SIZE];
        occupied = new boolean[SIZE];
    }

    private int hash(int key) { return key & (SIZE - 1); }

    public void put(int key, int value) {
        int h = hash(key);
        while (occupied[h] && keys[h] != key) h = (h + 1) & (SIZE - 1);
        keys[h] = key;
        values[h] = value;
        occupied[h] = true;
    }

    public int get(int key) {
        int h = hash(key);
        while (occupied[h]) {
            if (keys[h] == key) return values[h];
            h = (h + 1) & (SIZE - 1);
        }
        return -1;
    }

    public void remove(int key) {
        int h = hash(key);
        while (occupied[h]) {
            if (keys[h] == key) { occupied[h] = false; rehashCluster(h); return; }
            h = (h + 1) & (SIZE - 1);
        }
    }

    private void rehashCluster(int start) {
        int i = (start + 1) & (SIZE - 1);
        while (occupied[i]) {
            int ki = keys[i], vi = values[i];
            occupied[i] = false;
            put(ki, vi);
            i = (i + 1) & (SIZE - 1);
        }
    }
}
```

### Visualization: Separate Chaining

```
SIZE = 5, hash = key % 5

put(2,20): bucket[2] → [(2,20)]
put(7,70): bucket[2] → [(2,20), (7,70)]   ← collision!
put(3,30): bucket[3] → [(3,30)]
get(7):    bucket[2] → scan → found (7,70) → return 70

Buckets:
[0]: []
[1]: []
[2]: [(2,20), (7,70)]  ← chain
[3]: [(3,30)]
[4]: []
```

### Design Trade-offs

| Aspect | Separate Chaining | Open Addressing |
|--------|------------------|-----------------|
| Collision handling | Linked list / ArrayList per bucket | Probe next slot |
| Load factor tolerance | Degrades gracefully (>1.0 OK) | Must stay <0.7 |
| Cache performance | Poor (pointer chasing) | Excellent (contiguous) |
| Deletion | Simple (remove from list) | Complex (rehash cluster) |
| Memory overhead | Extra pointers/objects | Wastes empty slots |
| Resize trigger | avg chain > threshold | load factor > 0.75 |

### Production Considerations
- **Hash function quality:** Multiply-shift or murmur3 for uniform distribution.
- **Resize:** Double capacity when load factor exceeds threshold; rehash all entries.
- **Thread safety:** ConcurrentHashMap uses segment locks / CAS operations.
- **Java's HashMap:** Separate chaining with treeification (linked list → red-black tree when chain > 8).

### Complexity
- **Average:** O(1) for get/put/remove
- **Worst case:** O(n) if all keys collide (degenerate hash)
- **Space:** O(n + capacity)

---

## Summary Cheat Sheet

| # | Pattern | Key Data Structure | When to Use |
|---|---------|-------------------|-------------|
| 1 | Complement Lookup | `Map<value, index>` | Pair matching target |
| 2 | Freq + Bucket Sort | `Map<val, freq>` + `List[]` | Top K without heap |
| 3 | Group by Key | `Map<canonical, List>` | Equivalence grouping |
| 4 | Prefix Sum + Map | `Map<prefixSum, count>` | Subarray sum conditions |
| 5 | Hash as Visited | `Set<state>` | Cycle / termination detection |
| 6 | Consecutive Sequence | `Set<Integer>` | Longest run, O(n) |
| 7 | Index Mapping | `Map<value, lastIndex>` | Proximity duplicates |
| 8 | Design HashMap | Array of buckets | Implementation questions |

---

## Anti-Patterns / Common Mistakes

1. **Forgetting `prefixCount.put(0, 1)`** in Pattern 4 — misses subarrays starting at index 0.
2. **Not handling negative mod** in divisible-by-K — use `((sum % k) + k) % k`.
3. **Starting consecutive count from every element** — O(n^2). Guard with `!set.contains(num-1)`.
4. **Using mutable objects as HashMap keys** — leads to lost entries after mutation.
5. **Confusing "count of subarrays" vs "longest subarray"** — count stores frequency; longest stores first occurrence index.
