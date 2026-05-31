# Pattern 45: Interactive Problems

## Decision Flowchart

```
Interactive problem (query an API/judge)?
│
├─ Search for a value in sorted/structured space?
│   ├─ Sorted array / predicate → Binary Search Interactive
│   ├─ Bitonic/Mountain → Two binary searches
│   └─ 2D sorted matrix → Staircase from corner
│
├─ Identify an element among N candidates?
│   ├─ Pairwise elimination possible → Celebrity / Tournament
│   ├─ Each query eliminates fixed fraction → Binary partition
│   └─ Multi-outcome queries → Minimax / Information-theoretic
│
├─ Guess a secret (word/number)?
│   ├─ Ordered comparisons → Binary search
│   ├─ Match count feedback → Minimax elimination (Guess the Word)
│   └─ Bulls & Cows feedback → Query optimization
│
└─ Explore a graph/structure?
    ├─ Degree/neighbor queries → BFS with budget
    └─ Reachability queries → Binary partition on nodes
```

## Information Theory Foundation

```
Key principle: Each query provides at most log₂(outcomes) bits of information.
To distinguish among N candidates, you need at least ⌈log₂(N)⌉ queries.

Query Type           | Outcomes | Bits/Query | N elements needs
─────────────────────|──────────|────────────|─────────────────
Yes/No (boolean)     | 2        | 1 bit      | log₂(N) queries
Higher/Lower/Equal   | 3        | ~1.58 bits | log₃(N) queries
Match count (0..k)   | k+1      | log₂(k+1)  | varies
Subset membership    | 2        | 1 bit      | log₂(N) queries
```

**Adversarial thinking**: Assume the judge is adversarial — always prepare for the
worst-case partition. Maximize the *minimum* information gained per query.

---

## Pattern 1: Binary Search Interactive (Guess Number Higher/Lower)

### Signal
- Search space is ordered
- Query returns comparison result (higher/lower/equal)
- Query budget is O(log n)

### Template (Java)

```java
// LC 374: Guess Number Higher or Lower
// API: int guess(int num) → -1 (lower), 1 (higher), 0 (correct)
public class Solution extends GuessGame {
    public int guessNumber(int n) {
        int lo = 1, hi = n;
        while (lo <= hi) {
            int mid = lo + (hi - lo) / 2;
            int res = guess(mid);
            if (res == 0) return mid;
            else if (res == -1) hi = mid - 1;  // target is lower
            else lo = mid + 1;                  // target is higher
        }
        return -1; // unreachable
    }
}
```

### Key Insight
Each query eliminates half the search space → exactly 1 bit of information.
For n = 2³¹ - 1, worst case = 31 queries. Optimal and cannot be improved.

### Complexity
- Queries: O(log n)
- Space: O(1)

---

## Pattern 2: Find in Mountain Array

### Signal
- Array has bitonic structure (increases then decreases)
- No random access — must use API: `get(index)`, `length()`
- Minimize API calls

### Template (Java)

```java
// LC 1095: Find in Mountain Array
// API: int get(int index), int length()
class Solution {
    public int findInMountainArray(int target, MountainArray mountainArr) {
        int n = mountainArr.length();
        
        // Step 1: Find peak (binary search on slope)
        int lo = 0, hi = n - 1;
        while (lo < hi) {
            int mid = lo + (hi - lo) / 2;
            if (mountainArr.get(mid) < mountainArr.get(mid + 1))
                lo = mid + 1;  // ascending side
            else
                hi = mid;      // descending side or peak
        }
        int peak = lo;
        
        // Step 2: Binary search ascending side [0, peak]
        int result = binarySearch(mountainArr, target, 0, peak, true);
        if (result != -1) return result;
        
        // Step 3: Binary search descending side [peak+1, n-1]
        return binarySearch(mountainArr, target, peak + 1, n - 1, false);
    }
    
    private int binarySearch(MountainArray arr, int target, 
                             int lo, int hi, boolean ascending) {
        while (lo <= hi) {
            int mid = lo + (hi - lo) / 2;
            int val = arr.get(mid);
            if (val == target) return mid;
            if (ascending) {
                if (val < target) lo = mid + 1;
                else hi = mid - 1;
            } else {
                if (val > target) lo = mid + 1;
                else hi = mid - 1;
            }
        }
        return -1;
    }
}
```

### Key Insight
Three binary searches, each O(log n). Total queries ≤ 3·log₂(n).
Critical optimization: search ascending side first (return minimum index).
Cache `get()` calls if the API is expensive — each index queried at most once per search.

### Variants
- Find peak only (LC 852)
- Multiple targets in mountain array
- Rotated + mountain hybrid

### Complexity
- Queries: O(log n) — at most ~100 calls for n = 10⁴
- Space: O(1)

---

## Pattern 3: Interactive Graph Exploration

### Signal
- Graph structure unknown; discover via queries
- Query: "Is there an edge between u and v?" or "What are neighbors of u?"
- Find a specific node (sink, center, target)

### Template (Java)

```java
// Find a sink node (node with in-degree n-1, out-degree 0) interactively
// API: boolean hasEdge(int u, int v)
public int findSink(int n) {
    // Tournament elimination: maintain a candidate
    int candidate = 0;
    for (int i = 1; i < n; i++) {
        if (hasEdge(candidate, i)) {
            candidate = i;  // candidate has outgoing edge → can't be sink
        }
        // else: i has no incoming from candidate (or candidate has no edge to i)
    }
    
    // Verify candidate is actually a sink
    for (int i = 0; i < n; i++) {
        if (i == candidate) continue;
        if (!hasEdge(i, candidate) || hasEdge(candidate, i))
            return -1;  // no sink exists
    }
    return candidate;
}
```

### Key Insight
Tournament-style elimination: each query eliminates one candidate.
n-1 queries to find candidate + n-1 queries to verify = O(n) total.
This is optimal: any algorithm must query Ω(n) edges to confirm a sink.

### Complexity
- Queries: O(n)
- Space: O(1)

---

## Pattern 4: 20 Questions (Binary Partition of Search Space)

### Signal
- Universe of N items, identify the target
- Each query is a yes/no question about a property
- Budget: ⌈log₂(N)⌉ queries

### Template (Java)

```java
// General binary partition framework
// API: boolean query(Set<Integer> subset) → "Is target in this subset?"
public int twentyQuestions(int n) {
    List<Integer> candidates = IntStream.range(0, n)
        .boxed().collect(Collectors.toList());
    
    while (candidates.size() > 1) {
        int mid = candidates.size() / 2;
        // Partition into two halves — ask about the first half
        Set<Integer> firstHalf = new HashSet<>(candidates.subList(0, mid));
        
        if (query(firstHalf)) {
            candidates = candidates.subList(0, mid);
        } else {
            candidates = candidates.subList(mid, candidates.size());
        }
    }
    return candidates.get(0);
}
```

### Key Insight
**Balanced partition is optimal**: split candidates into two equal halves each query.
This guarantees ⌈log₂(N)⌉ queries regardless of adversary's answers.

Unbalanced partitions waste information:
- If you split 100 into (1, 99), "yes" gives ~7 bits but "no" gives ~0 bits.
- Expected info = H(1/100) ≈ 0.08 bits — terrible.
- Balanced split: expected info = 1 bit — optimal.

### Adversarial Argument
An adversary answers to maximize queries. Against balanced partition,
adversary cannot force more than ⌈log₂(N)⌉ queries — every answer eliminates half.

### Complexity
- Queries: ⌈log₂(N)⌉ (information-theoretically optimal)
- Space: O(N) for candidate list

---

## Pattern 5: Guess the Word (Minimax Strategy)

### Signal
- Secret word from a word list
- Query a word → get number of matching positions
- Limited queries (e.g., 10 queries for 100 words)
- Must eliminate maximum candidates per query

### Template (Java)

```java
// LC 843: Guess the Word
// API: int master.guess(String word) → number of exact char matches (0-6)
// If returns 6, you win. At most 10 calls allowed.
class Solution {
    public void findSecretWord(String[] wordlist, Master master) {
        List<String> candidates = new ArrayList<>(Arrays.asList(wordlist));
        
        for (int attempt = 0; attempt < 10 && candidates.size() > 0; attempt++) {
            // Pick word that minimizes worst-case remaining candidates
            String guess = minimaxPick(candidates);
            int matches = master.guess(guess);
            
            if (matches == 6) return;  // found it
            
            // Keep only words with exactly `matches` common positions with guess
            candidates = candidates.stream()
                .filter(w -> countMatches(guess, w) == matches)
                .collect(Collectors.toList());
        }
    }
    
    private String minimaxPick(List<String> candidates) {
        String best = candidates.get(0);
        int bestWorst = candidates.size();
        
        for (String word : candidates) {
            // Count how many candidates fall into each "match bucket"
            int[] buckets = new int[7]; // 0-6 matches
            for (String other : candidates) {
                buckets[countMatches(word, other)]++;
            }
            // Worst case: largest bucket (most candidates survive)
            int worst = Arrays.stream(buckets).max().getAsInt();
            if (worst < bestWorst) {
                bestWorst = worst;
                best = word;
            }
        }
        return best;
    }
    
    private int countMatches(String a, String b) {
        int count = 0;
        for (int i = 0; i < a.length(); i++)
            if (a.charAt(i) == b.charAt(i)) count++;
        return count;
    }
}
```

### Key Insight
**Minimax principle**: choose the guess that minimizes the maximum bucket size.
This guarantees the worst-case elimination is as large as possible.

Why not pick randomly? Random pick might leave 90% of candidates in one bucket.
Minimax ensures no outcome leaves more than ~N/7 candidates (for 7 outcomes: 0-6 matches).

**Heuristic alternative** (faster, nearly as good): pick word with most 0-match pairs.
Words with many 0-match neighbors tend to eliminate more candidates.

### Complexity
- Queries: O(10) — hard constraint
- Selection: O(N²·L) per guess where L = word length
- Space: O(N)

---

## Pattern 6: Find the Celebrity

### Signal
- N people at a party; celebrity is known by everyone but knows nobody
- Query: `knows(a, b)` → does person a know person b?
- Minimize total queries

### Template (Java)

```java
// LC 277: Find the Celebrity
// API: boolean knows(int a, int b)
public class Solution extends Relation {
    public int findCelebrity(int n) {
        // Phase 1: Elimination — find candidate in n-1 queries
        int candidate = 0;
        for (int i = 1; i < n; i++) {
            if (knows(candidate, i)) {
                candidate = i;
                // candidate knows i → candidate is NOT celebrity
                // i might be celebrity
            }
            // else: i is NOT celebrity (candidate doesn't know i)
        }
        
        // Phase 2: Verification — confirm in at most 2(n-1) queries
        for (int i = 0; i < n; i++) {
            if (i == candidate) continue;
            if (!knows(i, candidate) || knows(candidate, i))
                return -1;
        }
        return candidate;
    }
}
```

### Key Insight
**Each query eliminates exactly one candidate**:
- `knows(A, B) = true` → A is not celebrity
- `knows(A, B) = false` → B is not celebrity

Phase 1: n-1 queries eliminate n-1 people, leaving 1 candidate.
Phase 2: 2(n-1) queries verify (can optimize to n-1 with cached results).

Total: 3(n-1) queries. Lower bound: 3(n-1) - ⌈log₂n⌉ (proven optimal within constant).

### Complexity
- Queries: O(n) — exactly 3(n-1) worst case
- Space: O(1)

---

## Pattern 7: First Bad Version

### Signal
- Linear sequence of versions: good, good, ..., good, bad, bad, ..., bad
- Query: `isBadVersion(version)` → boolean
- Find the first bad version with minimum queries

### Template (Java)

```java
// LC 278: First Bad Version
// API: boolean isBadVersion(int version)
public class Solution extends VersionControl {
    public int firstBadVersion(int n) {
        int lo = 1, hi = n;
        while (lo < hi) {
            int mid = lo + (hi - lo) / 2;
            if (isBadVersion(mid))
                hi = mid;       // mid might be first bad
            else
                lo = mid + 1;   // mid is good, first bad is after
        }
        return lo;  // lo == hi == first bad version
    }
}
```

### Key Insight
Classic binary search on boolean predicate: `FFFFFTTTTT` — find first T.
Template difference from standard binary search:
- Use `lo < hi` (not `lo <= hi`)
- Never skip `mid` when predicate is true (`hi = mid`, not `hi = mid - 1`)
- Answer is `lo` when loop ends

This is the foundation of **all** binary search on predicates (monotonic functions).

### Complexity
- Queries: O(log n) — exactly ⌈log₂(n)⌉
- Space: O(1)

---

## Pattern 8: API Adapter Patterns (isBadVersion / Read4)

### Signal
- Given a limited API with fixed behavior (read 4 chars, check version)
- Must build higher-level functionality on top
- Buffer management for streaming APIs

### Template (Java)

```java
// LC 157/158: Read N Characters Given Read4
// API: int read4(char[] buf4) → reads up to 4 chars into buf4, returns count
// Build: int read(char[] buf, int n) → reads up to n chars

// Simple version (call once)
public class Solution extends Reader4 {
    public int read(char[] buf, int n) {
        char[] buf4 = new char[4];
        int totalRead = 0;
        
        while (totalRead < n) {
            int count = read4(buf4);
            int toCopy = Math.min(count, n - totalRead);
            System.arraycopy(buf4, 0, buf, totalRead, toCopy);
            totalRead += toCopy;
            if (count < 4) break;  // EOF reached
        }
        return totalRead;
    }
}

// Multiple calls version (must maintain state between calls)
public class Solution extends Reader4 {
    private char[] remainder = new char[4];
    private int remainderCount = 0;
    private int remainderOffset = 0;
    
    public int read(char[] buf, int n) {
        int totalRead = 0;
        
        // First, drain any buffered remainder from previous call
        while (totalRead < n && remainderOffset < remainderCount) {
            buf[totalRead++] = remainder[remainderOffset++];
        }
        
        // Then read fresh data
        char[] buf4 = new char[4];
        while (totalRead < n) {
            int count = read4(buf4);
            int toCopy = Math.min(count, n - totalRead);
            System.arraycopy(buf4, 0, buf, totalRead, toCopy);
            totalRead += toCopy;
            
            // Buffer any excess for next call
            if (toCopy < count) {
                remainderCount = count;
                remainderOffset = toCopy;
                System.arraycopy(buf4, 0, remainder, 0, count);
            }
            if (count < 4) break;
        }
        return totalRead;
    }
}
```

### Key Insight
**Adapter pattern**: wrap a fixed-size API to support variable-size operations.
Critical concerns:
1. **Buffering**: store unused data between calls
2. **EOF detection**: API returns less than max → no more data
3. **Boundary alignment**: requested size rarely aligns with API chunk size

### Complexity
- Queries to underlying API: O(n/4) = O(n)
- Space: O(1) buffer (4 chars)

---

## Pattern 9: Master Mind / Bulls and Cows (Query Optimization)

### Signal
- Guess a secret code; feedback is positional + non-positional matches
- Bulls (exact position) + Cows (right value, wrong position)
- Optimize number of guesses

### Template (Java)

```java
// LC 299: Bulls and Cows (evaluation side)
// When YOU are the judge — compute feedback for a guess
public String getHint(String secret, String guess) {
    int bulls = 0, cows = 0;
    int[] freq = new int[10]; // digit frequency
    
    for (int i = 0; i < secret.length(); i++) {
        if (secret.charAt(i) == guess.charAt(i)) {
            bulls++;
        } else {
            // If freq[s] < 0, guess had excess of s → cow
            if (freq[secret.charAt(i) - '0']++ < 0) cows++;
            // If freq[g] > 0, secret had excess of g → cow
            if (freq[guess.charAt(i) - '0']-- > 0) cows++;
        }
    }
    return bulls + "A" + cows + "B";
}

// Interactive solver: use minimax to pick optimal guess
public class MasterMindSolver {
    public String solve(List<String> allCodes, Guesser api) {
        List<String> candidates = new ArrayList<>(allCodes);
        
        while (candidates.size() > 1) {
            // Pick guess minimizing worst-case remaining candidates
            String guess = pickBestGuess(allCodes, candidates);
            String feedback = api.guess(guess);
            
            if (feedback.equals("4A0B")) return guess;
            
            candidates = candidates.stream()
                .filter(c -> getHint(c, guess).equals(feedback))
                .collect(Collectors.toList());
        }
        return candidates.get(0);
    }
    
    private String pickBestGuess(List<String> allCodes, List<String> candidates) {
        String best = null;
        int bestWorst = Integer.MAX_VALUE;
        
        // Consider ALL codes as potential guesses (not just candidates!)
        for (String code : allCodes) {
            Map<String, Integer> partitions = new HashMap<>();
            for (String cand : candidates) {
                String fb = getHint(cand, code);
                partitions.merge(fb, 1, Integer::sum);
            }
            int worst = partitions.values().stream().max(Integer::compare).orElse(0);
            if (worst < bestWorst) {
                bestWorst = worst;
                best = code;
            }
        }
        return best;
    }
}
```

### Key Insight
**Non-candidate guesses can be optimal**: Knuth proved that for 4-digit Mastermind,
starting with a non-candidate guess (e.g., "1122") guarantees solving in ≤ 5 guesses.

Feedback provides more than 1 bit: for k positions with d digits,
feedback has `C(k+1, 2)` possible values → up to ~3.9 bits for 4-digit codes.

**Information-theoretic lower bound**: `⌈log₂(d^k) / log₂(feedback_outcomes)⌉` guesses.
For 4-digit, 10-color: `⌈log₂(10⁴) / log₂(14)⌉ = ⌈13.3 / 3.8⌉ = 4` (achievable ≈ 5 avg).

### Complexity
- Guesses: O(k) worst case (5 for standard Mastermind)
- Per guess: O(|all| × |candidates|) for minimax selection
- Space: O(N) candidates

---

## Pattern 10: Interactive Matrix Search (Staircase Search)

### Signal
- Matrix sorted row-wise and column-wise
- Query: `matrix[i][j]` (or API equivalent)
- Find target with minimum queries

### Template (Java)

```java
// LC 240: Search a 2D Matrix II (interactive perspective)
// Matrix: rows sorted left→right, columns sorted top→bottom
// Start from top-right corner (or bottom-left)
public boolean searchMatrix(int[][] matrix, int target) {
    int m = matrix.length, n = matrix[0].length;
    int row = 0, col = n - 1;  // top-right corner
    
    while (row < m && col >= 0) {
        int val = matrix[row][col]; // This is our "query"
        if (val == target) return true;
        else if (val > target) col--;  // eliminate entire column
        else row++;                    // eliminate entire row
    }
    return false;
}
```

### Key Insight
**Why top-right (or bottom-left)?**
From top-right: going left decreases, going down increases → binary decision.
From top-left: both right and down increase → no elimination power.

Each query eliminates either an entire row or an entire column.
Worst case: m + n - 1 queries (walk from corner to opposite corner).

**Information perspective**: each query eliminates min(remaining_rows, remaining_cols)
elements. Not as efficient as binary search (which halves), but optimal for this structure.

### Complexity
- Queries: O(m + n)
- Space: O(1)

---

## Contest Template for Interactive Problems

```java
import java.util.*;
import java.io.*;

public class Main {
    static Scanner in = new Scanner(System.in);
    static PrintWriter out = new PrintWriter(System.out);
    
    // Query the judge — FLUSH after every query!
    static int query(int x) {
        out.println("? " + x);
        out.flush();  // CRITICAL: without flush, judge won't respond
        return in.nextInt();
    }
    
    // Submit final answer
    static void answer(int ans) {
        out.println("! " + ans);
        out.flush();
    }
    
    public static void main(String[] args) {
        int t = in.nextInt(); // number of test cases
        while (t-- > 0) {
            int n = in.nextInt();
            solve(n);
        }
        out.close();
    }
    
    static void solve(int n) {
        // Binary search example
        int lo = 1, hi = n;
        while (lo < hi) {
            int mid = lo + (hi - lo) / 2;
            int response = query(mid);
            if (response == 1) lo = mid + 1;    // target > mid
            else hi = mid;                       // target <= mid
        }
        answer(lo);
    }
}
```

### Contest Pitfalls

| Pitfall | Consequence | Fix |
|---------|-------------|-----|
| Forget `flush()` | TLE (judge waiting) | Flush after EVERY print |
| Exceed query limit | WA or RE | Count queries, assert budget |
| Off-by-one in binary search | Wrong answer | Test on n=1,2,3 |
| Read response after `!` | RE | Don't read after final answer |
| Print to stderr for debug | May confuse judge | Use `System.err` carefully |

---

## Query Budget Optimization

### Principle: Log₂(N) is the Floor, Not Always Achievable

```
Scenario              | Lower Bound      | Achievable
──────────────────────|──────────────────|────────────────
Sorted array, find x  | ⌈log₂(n)⌉       | ⌈log₂(n)⌉ ✓
Mountain array         | ⌈log₂(n)⌉       | ~3·log₂(n) ✗
Celebrity in n people  | Ω(n)            | 3(n-1) ✓
Guess word (6 chars)   | ⌈log₂(N)/2.8⌉  | ~10 (heuristic)
4-digit Mastermind     | 4               | 5 worst-case ✓
```

### Strategies to Reduce Queries

1. **Cache API results**: Never query the same input twice
2. **Derive info from structure**: If `a < b < c` and query(b) > target, skip a
3. **Batch information**: One multi-outcome query > multiple binary queries
4. **Probabilistic methods**: Randomized pivot can avoid adversarial worst case
5. **Amortization**: Across multiple targets, share elimination work

---

## Adversarial Thinking Framework

### When the Judge is Adaptive (Worst-Case Analysis)

Some problems have an **adaptive adversary** — the judge doesn't fix the answer
in advance but chooses responses to maximize your queries (while staying consistent).

**Defense**: Always reason about **what remains possible**, not what you "think" the answer is.

```java
// Framework: maintain a set of consistent candidates
Set<T> candidates = initialCandidates();
while (candidates.size() > 1) {
    // Choose query that guarantees maximum elimination
    // regardless of adversary's response
    Query q = chooseMinimax(candidates);
    Response r = ask(q);
    candidates = candidates.stream()
        .filter(c -> consistent(c, q, r))
        .collect(toSet());
}
return candidates.iterator().next();
```

### Minimax vs. Expected-Case Optimization

| Strategy | When to Use | Guarantee |
|----------|-------------|-----------|
| Minimax (worst-case) | Hard query budget, adversarial | Deterministic bound |
| Expected-case (entropy) | Soft budget, random target | Avg-case optimal |
| Randomized | Break adversary ties | Expected worst-case |

**Minimax**: Pick query minimizing `max(bucket_sizes)`.
**Entropy**: Pick query maximizing `H = -Σ (pᵢ · log₂ pᵢ)` over partition.

For contest problems with fixed budgets, always use **minimax**.

---

## Complete Pattern Comparison

| Pattern | Queries | Info/Query | Key Technique |
|---------|---------|------------|---------------|
| Binary Search | log₂(n) | 1 bit | Halving |
| Mountain Array | 3·log₂(n) | 1 bit | Three searches |
| Graph Sink | 3(n-1) | 1 elimination | Tournament |
| 20 Questions | log₂(N) | 1 bit | Balanced partition |
| Guess the Word | ≤10 | ~2.8 bits | Minimax buckets |
| Celebrity | 3(n-1) | 1 elimination | Pairwise elimination |
| First Bad Version | log₂(n) | 1 bit | Predicate search |
| Read4 Adapter | n/4 | 4 chars | Buffering |
| Bulls & Cows | ~5 | ~3.8 bits | Non-candidate guesses |
| Matrix Staircase | m+n-1 | 1 row/col | Corner start |

---

## Anti-Patterns

1. **Querying redundantly**: Never call API with same args twice — cache results
2. **Greedy without proof**: "Eliminate most on average" ≠ "best worst case"
3. **Forgetting flush**: #1 cause of TLE in interactive problems
4. **Not counting queries**: Always maintain a counter and assert < budget
5. **Assuming fixed answer**: Some judges are adaptive — maintain full candidate set
