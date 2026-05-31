# Monotonic Stack Patterns

## Core Idea

A **monotonic stack** maintains elements in strictly increasing or decreasing order. When a new element violates the monotonicity, we pop elements — and at that moment of popping, we've found the "answer" for those popped elements (their next greater/smaller, bounded range, etc.).

**Key Insight**: Every element is pushed once and popped once → O(n) total across all operations.

---

## Decision Flowchart

```
Need to find a "boundary" element for each position?
│
├─ YES → What kind of boundary?
│         │
│         ├─ Next Greater Element  → Decreasing stack, scan LEFT to RIGHT
│         ├─ Next Smaller Element  → Increasing stack, scan LEFT to RIGHT
│         ├─ Prev Greater Element  → Decreasing stack, scan LEFT to RIGHT (record on push)
│         ├─ Prev Smaller Element  → Increasing stack, scan LEFT to RIGHT (record on push)
│         │
│         └─ Need bounded range (histogram/contribution)?
│              → Compute BOTH PLE and NLE for each element
│
├─ Need to build optimal sequence (remove digits, subsequence)?
│         → Greedy with monotonic stack, control stack size
│
└─ Need to detect a pattern (132)?
          → Reverse scan with auxiliary variable tracking popped max
```

---

## The 4 Variants — Summary Table

| Variant | Stack Order | Scan Direction | Answer Recorded |
|---------|-------------|----------------|-----------------|
| **Next Greater** (NGE) | Decreasing (top=smallest) | Left → Right | On **pop** (current element is the answer for popped) |
| **Next Smaller** (NSE) | Increasing (top=largest) | Left → Right | On **pop** |
| **Previous Greater** (PGE) | Decreasing (top=smallest) | Left → Right | On **push** (stack top is the answer for current) |
| **Previous Smaller** (PSE) | Increasing (top=largest) | Left → Right | On **push** |

> **Mnemonic**: "Greater → Decreasing stack" (we keep a decreasing order so anything that breaks it IS the greater element). "Smaller → Increasing stack."

---

## Pattern 1: Next Greater Element (Right)

### Signal
- "For each element, find the first element to its **right** that is **greater**."
- LC 496, 503, 739

### Template (Java)

```java
public int[] nextGreaterElement(int[] nums) {
    int n = nums.length;
    int[] result = new int[n];
    Arrays.fill(result, -1); // default: no greater element
    Deque<Integer> stack = new ArrayDeque<>(); // stores INDICES
    
    for (int i = 0; i < n; i++) {
        // Pop all elements smaller than current — current is their NGE
        while (!stack.isEmpty() && nums[stack.peek()] < nums[i]) {
            result[stack.pop()] = nums[i];
        }
        stack.push(i);
    }
    return result;
}
```

### Step-by-Step Trace

**Input**: `[2, 1, 2, 4, 3]`

```
i=0, nums[0]=2
  Stack empty → push 0
  Stack (bottom→top): [0(2)]

i=1, nums[1]=1
  1 < 2 (top) → no pop
  Push 1
  Stack: [0(2), 1(1)]

i=2, nums[2]=2
  2 > 1 (top) → pop index 1 → result[1] = 2
  2 ≥ 2 (top)? No, 2 < 2 is false but 2 is NOT > 2 → stop (strictly greater)
  Wait: condition is nums[stack.peek()] < nums[i] → 2 < 2? NO → stop
  Push 2
  Stack: [0(2), 2(2)]

i=3, nums[3]=4
  4 > 2 (top, index 2) → pop index 2 → result[2] = 4
  4 > 2 (top, index 0) → pop index 0 → result[0] = 4
  Stack empty → stop
  Push 3
  Stack: [3(4)]

i=4, nums[4]=3
  3 < 4 (top) → no pop
  Push 4
  Stack: [3(4), 4(3)]

Remaining in stack: indices 3, 4 → result stays -1

RESULT: [4, 2, 4, -1, -1]
```

### Complexity
- **Time**: O(n) — each element pushed/popped at most once
- **Space**: O(n) — stack

---

## Pattern 2: Next Smaller Element (Right)

### Signal
- "For each element, find the first element to its **right** that is **smaller**."

### Template (Java)

```java
public int[] nextSmallerElement(int[] nums) {
    int n = nums.length;
    int[] result = new int[n];
    Arrays.fill(result, -1);
    Deque<Integer> stack = new ArrayDeque<>(); // increasing stack
    
    for (int i = 0; i < n; i++) {
        while (!stack.isEmpty() && nums[stack.peek()] > nums[i]) {
            result[stack.pop()] = nums[i];
        }
        stack.push(i);
    }
    return result;
}
```

> Only difference from NGE: stack maintains **increasing** order; pop condition flips to `>`.

---

## Pattern 3: Previous Greater Element (Left Scan)

### Signal
- "For each element, find the nearest element to its **left** that is **greater**."

### Template (Java)

```java
public int[] previousGreaterElement(int[] nums) {
    int n = nums.length;
    int[] result = new int[n];
    Arrays.fill(result, -1);
    Deque<Integer> stack = new ArrayDeque<>(); // decreasing stack
    
    for (int i = 0; i < n; i++) {
        // Maintain decreasing: pop elements ≤ current (they can't be PGE for future)
        while (!stack.isEmpty() && nums[stack.peek()] <= nums[i]) {
            stack.pop();
        }
        // Answer is whatever remains on top (first greater to the left)
        if (!stack.isEmpty()) {
            result[i] = nums[stack.peek()];
        }
        stack.push(i);
    }
    return result;
}
```

> **Key difference**: Answer is recorded **on push** (stack top = answer for current), not on pop.

---

## Pattern 4: Previous Smaller Element (Left Scan)

### Template (Java)

```java
public int[] previousSmallerElement(int[] nums) {
    int n = nums.length;
    int[] result = new int[n];
    Arrays.fill(result, -1);
    Deque<Integer> stack = new ArrayDeque<>(); // increasing stack
    
    for (int i = 0; i < n; i++) {
        while (!stack.isEmpty() && nums[stack.peek()] >= nums[i]) {
            stack.pop();
        }
        if (!stack.isEmpty()) {
            result[i] = nums[stack.peek()];
        }
        stack.push(i);
    }
    return result;
}
```

---

## Pattern 5: Daily Temperatures (LC 739)

### Signal
- "How many days until a warmer temperature?" — this is NGE but return **distance** not value.

### Template (Java)

```java
public int[] dailyTemperatures(int[] temps) {
    int n = temps.length;
    int[] result = new int[n];
    Deque<Integer> stack = new ArrayDeque<>();
    
    for (int i = 0; i < n; i++) {
        while (!stack.isEmpty() && temps[stack.peek()] < temps[i]) {
            int idx = stack.pop();
            result[idx] = i - idx; // distance, not value
        }
        stack.push(i);
    }
    return result;
}
```

### Trace

**Input**: `[73, 74, 75, 71, 69, 72, 76, 73]`

```
i=0: push 0.           Stack: [0(73)]
i=1: 74>73 → pop 0, result[0]=1-0=1. Push 1.    Stack: [1(74)]
i=2: 75>74 → pop 1, result[1]=2-1=1. Push 2.    Stack: [2(75)]
i=3: 71<75 → push 3.  Stack: [2(75), 3(71)]
i=4: 69<71 → push 4.  Stack: [2(75), 3(71), 4(69)]
i=5: 72>69 → pop 4, result[4]=5-4=1
     72>71 → pop 3, result[3]=5-3=2
     72<75 → stop. Push 5.  Stack: [2(75), 5(72)]
i=6: 76>72 → pop 5, result[5]=6-5=1
     76>75 → pop 2, result[2]=6-2=4
     Push 6.  Stack: [6(76)]
i=7: 73<76 → push 7.  Stack: [6(76), 7(73)]

Remaining: result[6]=0, result[7]=0

RESULT: [1, 1, 4, 2, 1, 1, 0, 0]
```

---

## Pattern 6: Largest Rectangle in Histogram (LC 84)

### Signal
- "Find the largest rectangle that can be formed in a histogram."
- Each bar can extend left/right until a shorter bar is encountered → need PSE and NSE.

### Template (Java)

```java
public int largestRectangleArea(int[] heights) {
    int n = heights.length;
    Deque<Integer> stack = new ArrayDeque<>();
    int maxArea = 0;
    
    for (int i = 0; i <= n; i++) {
        int currHeight = (i == n) ? 0 : heights[i]; // sentinel
        
        while (!stack.isEmpty() && heights[stack.peek()] > currHeight) {
            int h = heights[stack.pop()];
            int width = stack.isEmpty() ? i : i - stack.peek() - 1;
            maxArea = Math.max(maxArea, h * width);
        }
        stack.push(i);
    }
    return maxArea;
}
```

**Why it works**: When we pop index `j` because `heights[i] < heights[j]`:
- `i` is the **Next Smaller** to the right of `j`
- `stack.peek()` (after pop) is the **Previous Smaller** to the left of `j`
- Width = `i - stack.peek() - 1`

### Extension: Maximal Rectangle in Binary Matrix (LC 85)

Build a histogram for each row and apply Largest Rectangle on each.

```java
public int maximalRectangle(char[][] matrix) {
    if (matrix.length == 0) return 0;
    int cols = matrix[0].length;
    int[] heights = new int[cols];
    int maxArea = 0;
    
    for (char[] row : matrix) {
        // Build histogram: if '1', increment; if '0', reset to 0
        for (int j = 0; j < cols; j++) {
            heights[j] = (row[j] == '1') ? heights[j] + 1 : 0;
        }
        maxArea = Math.max(maxArea, largestRectangleArea(heights));
    }
    return maxArea;
}
```

**Complexity**: O(rows * cols) time, O(cols) space.

---

## Pattern 7: Trapping Rain Water (LC 42)

### Signal
- "How much water can be trapped between bars?"

### Monotonic Stack Approach (Decreasing Stack)

When we find a bar taller than the top, water is trapped in the "valley" between current bar, popped bar, and new top.

```java
public int trap(int[] height) {
    Deque<Integer> stack = new ArrayDeque<>(); // decreasing
    int water = 0;
    
    for (int i = 0; i < height.length; i++) {
        while (!stack.isEmpty() && height[i] > height[stack.peek()]) {
            int bottom = height[stack.pop()];
            if (stack.isEmpty()) break; // no left wall
            int leftWall = stack.peek();
            int width = i - leftWall - 1;
            int boundedHeight = Math.min(height[i], height[leftWall]) - bottom;
            water += width * boundedHeight;
        }
        stack.push(i);
    }
    return water;
}
```

**Intuition**: We compute water layer by layer (horizontal slices) as we encounter right boundaries.

---

## Pattern 8: Stock Span (LC 901)

### Signal
- "Consecutive days (including today) where price was ≤ today's price." — Online/streaming.
- This is equivalent to: distance to **Previous Greater Element**.

### Template (Java)

```java
class StockSpanner {
    Deque<int[]> stack; // [price, span]
    
    public StockSpanner() {
        stack = new ArrayDeque<>();
    }
    
    public int next(int price) {
        int span = 1;
        // Pop days with price ≤ current; absorb their spans
        while (!stack.isEmpty() && stack.peek()[0] <= price) {
            span += stack.pop()[1];
        }
        stack.push(new int[]{price, span});
        return span;
    }
}
```

**Why spans accumulate**: Each popped element's span represents days already "absorbed" — we don't need individual indices.

---

## Pattern 9: Remove K Digits (LC 402)

### Signal
- "Remove k digits to make the number as small as possible."
- Build a **monotonically increasing** sequence (smallest number = non-decreasing digits from left).

### Template (Java)

```java
public String removeKdigits(String num, int k) {
    Deque<Character> stack = new ArrayDeque<>();
    
    for (char c : num.toCharArray()) {
        while (k > 0 && !stack.isEmpty() && stack.peek() > c) {
            stack.pop();
            k--;
        }
        stack.push(c);
    }
    
    // If k remaining, remove from end (they're the largest in increasing seq)
    while (k-- > 0) stack.pop();
    
    // Build result, strip leading zeros
    StringBuilder sb = new StringBuilder();
    while (!stack.isEmpty()) sb.append(stack.pollLast());
    while (sb.length() > 1 && sb.charAt(0) == '0') sb.deleteCharAt(0);
    
    return sb.length() == 0 ? "0" : sb.toString();
}
```

---

## Pattern 10: 132 Pattern (LC 456)

### Signal
- "Find indices i < j < k such that nums[i] < nums[k] < nums[j]."
- Reverse scan: maintain decreasing stack for candidates of `nums[j]`; track `nums[k]` as the max popped value.

### Template (Java)

```java
public boolean find132pattern(int[] nums) {
    int n = nums.length;
    Deque<Integer> stack = new ArrayDeque<>(); // candidates for "3" (nums[j])
    int third = Integer.MIN_VALUE; // max candidate for "2" (nums[k])
    
    for (int i = n - 1; i >= 0; i--) {
        // Check if current can be "1" (nums[i] < third means pattern found)
        if (nums[i] < third) return true;
        
        // Pop elements smaller than nums[i] — they become candidates for "2"
        while (!stack.isEmpty() && stack.peek() < nums[i]) {
            third = Math.max(third, stack.pop());
        }
        stack.push(nums[i]); // current is candidate for "3"
    }
    return false;
}
```

**Insight**: Scanning right-to-left, the stack holds potential "3" values (j-position). When we pop something smaller than current, it becomes the best "2" candidate (k-position). If any future element (further left) is less than our "2" candidate, we've found the pattern.

---

## Pattern 11: Sum of Subarray Minimums (LC 907)

### Signal
- "Sum of min(subarray) for all subarrays." — **Contribution technique**.
- For each element, determine how many subarrays it is the minimum of.

### Key Idea
For element at index `i`:
- **PLE** (Previous Less Element): index of nearest smaller to the left → `left[i]`
- **NLE** (Next Less Element): index of nearest smaller to the right → `right[i]`
- Element `nums[i]` is the minimum for `(i - left[i]) * (right[i] - i)` subarrays.

### Template (Java)

```java
public int sumSubarrayMins(int[] arr) {
    int MOD = 1_000_000_007;
    int n = arr.length;
    int[] left = new int[n];  // distance to PLE
    int[] right = new int[n]; // distance to NLE
    
    Deque<Integer> stack = new ArrayDeque<>();
    
    // PLE: strictly less (use <= to handle duplicates: left takes strict <)
    for (int i = 0; i < n; i++) {
        while (!stack.isEmpty() && arr[stack.peek()] >= arr[i]) stack.pop();
        left[i] = stack.isEmpty() ? i + 1 : i - stack.peek();
        stack.push(i);
    }
    
    stack.clear();
    
    // NLE: less or equal (use < to handle duplicates: right takes <=)
    for (int i = n - 1; i >= 0; i--) {
        while (!stack.isEmpty() && arr[stack.peek()] > arr[i]) stack.pop();
        right[i] = stack.isEmpty() ? n - i : stack.peek() - i;
        stack.push(i);
    }
    
    long sum = 0;
    for (int i = 0; i < n; i++) {
        sum = (sum + (long) arr[i] * left[i] % MOD * right[i]) % MOD;
    }
    return (int) sum;
}
```

> **Duplicate handling**: Use strict `<` on one side and `<=` on the other to avoid double-counting subarrays where multiple elements share the minimum value.

---

## Pattern 12: Circular Variant — Next Greater Element II (LC 503)

### Signal
- "Array is circular — the next greater element can wrap around."

### Template (Java)

```java
public int[] nextGreaterElements(int[] nums) {
    int n = nums.length;
    int[] result = new int[n];
    Arrays.fill(result, -1);
    Deque<Integer> stack = new ArrayDeque<>();
    
    // Iterate 2n to simulate circular array
    for (int i = 0; i < 2 * n; i++) {
        int idx = i % n;
        while (!stack.isEmpty() && nums[stack.peek()] < nums[idx]) {
            result[stack.pop()] = nums[idx];
        }
        if (i < n) stack.push(i); // only push in first pass
    }
    return result;
}
```

**Why 2n**: Second pass allows elements remaining in the stack from the first pass to find their NGE from the beginning of the array.

---

## Unified Mental Model

```
┌─────────────────────────────────────────────────────┐
│                   MONOTONIC STACK                     │
├─────────────────────────────────────────────────────┤
│                                                       │
│  INVARIANT: Stack always monotonic after each step    │
│                                                       │
│  On PUSH: "Who is my nearest boundary to the LEFT?"  │
│           → Answer = current stack top (PGE/PSE)      │
│                                                       │
│  On POP:  "Who is my nearest boundary to the RIGHT?" │
│           → Answer = element causing the pop (NGE/NSE)│
│                                                       │
│  RANGE:   Both at once → width for histogram/contrib  │
│           pop gives right boundary + new top = left   │
│                                                       │
└─────────────────────────────────────────────────────┘
```

---

## Complexity Summary

| Pattern | Time | Space |
|---------|------|-------|
| All NGE/NSE/PGE/PSE variants | O(n) | O(n) |
| Daily Temperatures | O(n) | O(n) |
| Largest Rectangle in Histogram | O(n) | O(n) |
| Maximal Rectangle (2D) | O(m*n) | O(n) |
| Trapping Rain Water | O(n) | O(n) |
| Stock Span (per call amortized) | O(1) | O(n) |
| Remove K Digits | O(n) | O(n) |
| 132 Pattern | O(n) | O(n) |
| Sum of Subarray Minimums | O(n) | O(n) |
| Next Greater Element II (circular) | O(n) | O(n) |

---

## Common Pitfalls

1. **Store indices, not values** — almost always need indices for distance/width calculations.
2. **Sentinel trick** — append `0` (or `Integer.MIN_VALUE`) to force final flush of the stack (histogram pattern).
3. **Duplicate handling** — in contribution problems, use strict `<` on one boundary and `<=` on the other.
4. **Stack stores candidates** — elements still "waiting" for their answer. Once popped, they're resolved.
5. **Circular** — iterate `2n` but only push indices in the first `n`.
