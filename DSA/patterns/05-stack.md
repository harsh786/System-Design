# Stack - Pattern Guide

---

## Pattern Recognition Signals

| Signal | Pattern |
|--------|---------|
| Valid/matching brackets | Stack matching |
| Next greater/smaller element | Monotonic Stack |
| Largest rectangle in histogram | Monotonic Stack |
| Evaluate expression (+,-,*,/,()) | Stack + operator precedence |
| Undo / backspace / collision | Simulation stack |
| Build smallest number removing K | Greedy + Monotonic Stack |
| Decode nested `3[a2[c]]` | Stack of context |
| O(1) getMin | Auxiliary min-stack |

---

## Pattern 1: Bracket Matching / Validation

**When:** Check if parentheses are valid, find longest valid, min additions.

### Template
```java
Deque<Character> stack = new ArrayDeque<>();
Map<Character, Character> map = Map.of(')', '(', ']', '[', '}', '{');

for (char c : s.toCharArray()) {
    if (map.containsValue(c)) {
        stack.push(c);           // opening bracket
    } else {
        if (stack.isEmpty() || stack.peek() != map.get(c)) return false;
        stack.pop();
    }
}
return stack.isEmpty();
```

### Variants

**Longest Valid Parentheses:**
```java
Deque<Integer> stack = new ArrayDeque<>();
stack.push(-1);  // base for length calculation
int maxLen = 0;
for (int i = 0; i < s.length(); i++) {
    if (s.charAt(i) == '(') {
        stack.push(i);
    } else {
        stack.pop();
        if (stack.isEmpty()) stack.push(i);  // new base
        else maxLen = Math.max(maxLen, i - stack.peek());
    }
}
```

**Minimum Add to Make Valid:**
```java
int open = 0, close = 0;
for (char c : s.toCharArray()) {
    if (c == '(') open++;
    else if (open > 0) open--;
    else close++;
}
return open + close;  // unmatched opens + unmatched closes
```

---

## Pattern 2: Monotonic Stack (Next Greater/Smaller)

**When:** For each element, find the next element that is greater (or smaller).

### Template: Next Greater Element
```java
int[] result = new int[n];
Arrays.fill(result, -1);
Deque<Integer> stack = new ArrayDeque<>();  // stores INDICES

for (int i = 0; i < n; i++) {
    while (!stack.isEmpty() && nums[i] > nums[stack.peek()]) {
        result[stack.pop()] = nums[i];  // i is the next greater
    }
    stack.push(i);
}
```

### All Four Variants
```
┌────────────────────────────────────────────────────────────┐
│ Direction  │ Looking For      │ Stack Order    │ Pop When   │
├────────────┼──────────────────┼───────────────┼────────────┤
│ Left→Right │ Next GREATER     │ Decreasing ↓  │ curr > top │
│ Left→Right │ Next SMALLER     │ Increasing ↑  │ curr < top │
│ Right→Left │ Previous GREATER │ Decreasing ↓  │ curr > top │
│ Right→Left │ Previous SMALLER │ Increasing ↑  │ curr < top │
└────────────────────────────────────────────────────────────┘
```

### Circular Array (Next Greater Element II)
```java
int[] result = new int[n];
Arrays.fill(result, -1);
Deque<Integer> stack = new ArrayDeque<>();

for (int i = 0; i < 2 * n; i++) {      // iterate twice for circular
    int idx = i % n;
    while (!stack.isEmpty() && nums[idx] > nums[stack.peek()]) {
        result[stack.pop()] = nums[idx];
    }
    if (i < n) stack.push(i);           // only push first round
}
```

### Visualization
```
nums: [2, 1, 2, 4, 3]
Goal: Next Greater Element for each

i=0 (2): stack=[], push 0         stack=[0]
i=1 (1): 1<2, push 1              stack=[0,1]     (decreasing: 2,1)
i=2 (2): 2>1 → pop 1→result[1]=2  stack=[0]
          2≥2 → pop 0→result[0]=2  stack=[]
          push 2                    stack=[2]
i=3 (4): 4>2 → pop 2→result[2]=4  stack=[]
          push 3                    stack=[3]
i=4 (3): 3<4, push 4              stack=[3,4]

result: [2, 2, 4, -1, -1]
```

**Complexity:** O(n) — each element pushed and popped at most once

---

## Pattern 3: Largest Rectangle in Histogram

**When:** Find largest rectangular area under histogram bars.

### Template
```java
Deque<Integer> stack = new ArrayDeque<>();
stack.push(-1);  // sentinel for width calculation
int maxArea = 0;

for (int i = 0; i <= heights.length; i++) {
    int h = (i == heights.length) ? 0 : heights[i];  // sentinel bar
    while (stack.peek() != -1 && h <= heights[stack.peek()]) {
        int height = heights[stack.pop()];
        int width = i - stack.peek() - 1;
        maxArea = Math.max(maxArea, height * width);
    }
    stack.push(i);
}
return maxArea;
```

### Visualization
```
heights: [2, 1, 5, 6, 2, 3]

    6
    5 █ 
    4 █ █
    3 █ █     █
    2 █ █ █ █ █ █
    1 █ █ █ █ █ █
      ─────────────
      2 1 5 6 2 3

Largest rectangle: height=5, width=2 (columns 2-3) → area=10

When we encounter h=2 at index 4:
  Pop 6 (idx=3): width = 4-2-1 = 1, area = 6*1 = 6
  Pop 5 (idx=2): width = 4-1-1 = 2, area = 5*2 = 10 ← MAX
```

### Extension: Maximal Rectangle in 2D Matrix
```java
// For each row, build histogram heights (accumulate upward)
// Apply largest rectangle algorithm on each row's histogram
for (int i = 0; i < rows; i++) {
    for (int j = 0; j < cols; j++) {
        heights[j] = (matrix[i][j] == '1') ? heights[j] + 1 : 0;
    }
    maxArea = Math.max(maxArea, largestRectangle(heights));
}
```

---

## Pattern 4: Expression Evaluation (Calculator)

**When:** Parse and evaluate arithmetic expressions.

### Basic Calculator II (no parentheses, +,-,*,/)
```java
Deque<Integer> stack = new ArrayDeque<>();
int num = 0;
char op = '+';

for (int i = 0; i <= s.length(); i++) {
    char c = (i < s.length()) ? s.charAt(i) : '+';
    if (Character.isDigit(c)) {
        num = num * 10 + (c - '0');
    } else if (c != ' ') {
        switch (op) {
            case '+': stack.push(num); break;
            case '-': stack.push(-num); break;
            case '*': stack.push(stack.pop() * num); break;
            case '/': stack.push(stack.pop() / num); break;
        }
        op = c;
        num = 0;
    }
}
// Sum all values in stack
```

### Basic Calculator I (with parentheses, +,-)
```java
Deque<Integer> stack = new ArrayDeque<>();
int num = 0, result = 0, sign = 1;

for (char c : s.toCharArray()) {
    if (Character.isDigit(c)) {
        num = num * 10 + (c - '0');
    } else if (c == '+' || c == '-') {
        result += sign * num;
        sign = (c == '+') ? 1 : -1;
        num = 0;
    } else if (c == '(') {
        stack.push(result);
        stack.push(sign);
        result = 0; sign = 1;
    } else if (c == ')') {
        result += sign * num;
        num = 0;
        result *= stack.pop();  // sign before paren
        result += stack.pop();  // result before paren
    }
}
return result + sign * num;
```

### Operator Precedence Strategy
```
No parens: * and / applied immediately (pop from stack and compute)
           + and - just push (compute at end with sum)

With parens: '(' pushes context (result + sign) → recursive thinking
             ')' pops and combines
```

---

## Pattern 5: Stack for Simulation / Undo

**When:** Asteroid collision, backspace string compare, browser history.

### Asteroid Collision
```java
Deque<Integer> stack = new ArrayDeque<>();
for (int a : asteroids) {
    boolean alive = true;
    while (alive && !stack.isEmpty() && a < 0 && stack.peek() > 0) {
        if (stack.peek() < -a) stack.pop();         // top destroyed
        else if (stack.peek() == -a) { stack.pop(); alive = false; }
        else alive = false;                          // current destroyed
    }
    if (alive) stack.push(a);
}
```

### Backspace String Compare
```java
// Using stack: push chars, pop on '#'
// O(1) space: iterate from end, count backspaces
int i = s.length()-1, j = t.length()-1;
int skipS = 0, skipT = 0;
while (i >= 0 || j >= 0) {
    while (i >= 0 && (s.charAt(i) == '#' || skipS > 0)) {
        if (s.charAt(i) == '#') skipS++; else skipS--;
        i--;
    }
    // same for j...
    // compare s[i] with t[j]
}
```

---

## Pattern 6: Min Stack / Max Stack

**When:** O(1) push, pop, top, AND getMin.

### Template
```java
class MinStack {
    Deque<int[]> stack = new ArrayDeque<>();  // [value, currentMin]
    
    void push(int val) {
        int min = stack.isEmpty() ? val : Math.min(val, stack.peek()[1]);
        stack.push(new int[]{val, min});
    }
    
    void pop() { stack.pop(); }
    int top() { return stack.peek()[0]; }
    int getMin() { return stack.peek()[1]; }
}
```

### Space-Optimized (store diff from min)
```java
// Store (value - min) instead. If negative, the value IS the new min.
// On pop: if top < 0, previous min = currentMin - top
```

---

## Pattern 7: Remove K Digits / Build Optimal Number

**When:** Build smallest/largest number by removing K digits, or remove duplicate letters maintaining order.

### Remove K Digits
```java
Deque<Character> stack = new ArrayDeque<>();
for (char c : num.toCharArray()) {
    while (k > 0 && !stack.isEmpty() && stack.peek() > c) {
        stack.pop();
        k--;
    }
    stack.push(c);
}
while (k-- > 0) stack.pop();  // remove remaining from end
// Build result, strip leading zeros
```

### Remove Duplicate Letters (Smallest in Order)
```java
int[] count = new int[26];       // remaining count
boolean[] inStack = new boolean[26];
for (char c : s.toCharArray()) count[c - 'a']++;

Deque<Character> stack = new ArrayDeque<>();
for (char c : s.toCharArray()) {
    count[c - 'a']--;
    if (inStack[c - 'a']) continue;
    while (!stack.isEmpty() && stack.peek() > c && count[stack.peek()-'a'] > 0) {
        inStack[stack.pop() - 'a'] = false;
    }
    stack.push(c);
    inStack[c - 'a'] = true;
}
```

---

## Pattern 8: Daily Temperatures / Stock Span

### Daily Temperatures (days until warmer)
```java
int[] result = new int[n];
Deque<Integer> stack = new ArrayDeque<>();
for (int i = 0; i < n; i++) {
    while (!stack.isEmpty() && temps[i] > temps[stack.peek()]) {
        int prev = stack.pop();
        result[prev] = i - prev;
    }
    stack.push(i);
}
```

### Online Stock Span (consecutive days price ≤ today)
```java
class StockSpanner {
    Deque<int[]> stack = new ArrayDeque<>();  // [price, span]
    
    int next(int price) {
        int span = 1;
        while (!stack.isEmpty() && stack.peek()[0] <= price) {
            span += stack.pop()[1];  // absorb previous spans
        }
        stack.push(new int[]{price, span});
        return span;
    }
}
```

---

## Summary Flowchart

```
Stack Problem?
│
├─ Matching brackets? ──────────→ Push open, pop on close, validate
│
├─ Next greater/smaller? ───────→ Monotonic stack (decreasing/increasing)
│
├─ Largest rectangle? ──────────→ Monotonic stack + area calculation
│
├─ Evaluate expression? ────────→ Stack + operator precedence
│
├─ Collision/undo/backspace? ──→ Simulate with push/pop
│
├─ O(1) min/max tracking? ─────→ Auxiliary stack or pair encoding
│
├─ Build optimal sequence? ────→ Greedy pop from stack when better available
│
└─ Nested decode? ─────────────→ Push context on '[', restore on ']'
```
