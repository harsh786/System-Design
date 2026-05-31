# Stack Patterns (Classical)

## Decision Flowchart

```
Problem involves...
│
├─ Matching/nesting brackets or tags?
│   └─ Pattern 1: Bracket Matching
│
├─ Evaluate expression with operators?
│   ├─ No parentheses → Pattern 2: Basic Calculator
│   └─ Has parentheses → Pattern 3: Recursive / Context Save
│
├─ Track min/max in O(1) alongside push/pop?
│   └─ Pattern 4: Min/Max Stack
│
├─ Simulate process where later items cancel earlier?
│   └─ Pattern 5: Simulation/Undo
│
├─ Nested encoding like k[string]?
│   └─ Pattern 6: Decode Nested Strings
│
├─ Build optimal sequence by greedily removing elements?
│   ├─ Minimize number (remove k digits) → Pattern 7
│   └─ Unique chars, smallest order → Pattern 8
│
└─ Needs monotonic property (next greater/smaller)?
    └─ See 06-monotonic-stack.md
```

---

## Pattern 1: Bracket Matching / Validation

### Signal
- "Valid parentheses", balanced brackets, longest valid substring
- Any nesting structure: `()`, `[]`, `{}`, HTML tags

### Template (Java)

```java
// LC 20: Valid Parentheses
public boolean isValid(String s) {
    Deque<Character> stack = new ArrayDeque<>();
    for (char c : s.toCharArray()) {
        if (c == '(') stack.push(')');
        else if (c == '[') stack.push(']');
        else if (c == '{') stack.push('}');
        else {
            if (stack.isEmpty() || stack.pop() != c) return false;
        }
    }
    return stack.isEmpty();
}

// LC 32: Longest Valid Parentheses
public int longestValidParentheses(String s) {
    Deque<Integer> stack = new ArrayDeque<>();
    stack.push(-1); // sentinel: last unmatched index
    int max = 0;
    for (int i = 0; i < s.length(); i++) {
        if (s.charAt(i) == '(') {
            stack.push(i);
        } else {
            stack.pop();
            if (stack.isEmpty()) {
                stack.push(i); // new sentinel
            } else {
                max = Math.max(max, i - stack.peek());
            }
        }
    }
    return max;
}
```

### Visualization

```
Input: "( { [ ] } )"

Step-by-step:
  char '(' → push ')'       stack: [')']
  char '{' → push '}'       stack: [')', '}']
  char '[' → push ']'       stack: [')', '}', ']']
  char ']' → pop ']' ✓      stack: [')', '}']
  char '}' → pop '}' ✓      stack: [')']
  char ')' → pop ')' ✓      stack: []
  
  stack empty → VALID

Longest Valid (index-based):
  s = "( ) ( ( )"
  idx  0 1 2 3 4
  
  stack starts: [-1]
  i=0 '(' push 0       → [-1, 0]
  i=1 ')' pop→0, len=1-(-1)=2, max=2  → [-1]
  i=2 '(' push 2       → [-1, 2]
  i=3 '(' push 3       → [-1, 2, 3]
  i=4 ')' pop→3, len=4-2=2, max=2     → [-1, 2]
  
  Answer: 2
```

### Variants
| Problem | Key Twist |
|---------|-----------|
| LC 20 Valid Parentheses | Basic matching |
| LC 32 Longest Valid Parentheses | Index stack + sentinel |
| LC 1249 Min Remove to Make Valid | Track indices to remove |
| LC 921 Min Add to Make Valid | Count unmatched |
| LC 394 partially (nesting) | Combined with decode |

### Complexity
- Time: O(n) single pass
- Space: O(n) worst case (all openers)

---

## Pattern 2: Expression Evaluation — Basic Calculator (No Parentheses)

### Signal
- Evaluate arithmetic string with `+`, `-`, `*`, `/`
- Operator precedence: `*` and `/` before `+` and `-`

### Template (Java)

```java
// LC 227: Basic Calculator II — no parentheses, has */
public int calculate(String s) {
    Deque<Integer> stack = new ArrayDeque<>();
    int num = 0;
    char prevOp = '+';
    
    for (int i = 0; i < s.length(); i++) {
        char c = s.charAt(i);
        if (Character.isDigit(c)) {
            num = num * 10 + (c - '0');
        }
        // Process when we hit operator or end of string
        if ((!Character.isDigit(c) && c != ' ') || i == s.length() - 1) {
            switch (prevOp) {
                case '+': stack.push(num); break;
                case '-': stack.push(-num); break;
                case '*': stack.push(stack.pop() * num); break;
                case '/': stack.push(stack.pop() / num); break;
            }
            prevOp = c;
            num = 0;
        }
    }
    
    int result = 0;
    for (int val : stack) result += val;
    return result;
}
```

### Visualization

```
Input: "3 + 2 * 2 - 1"

prevOp='+', num building:

  '3' → num=3
  '+' → prevOp was '+', push 3.    stack: [3].     prevOp='+'
  '2' → num=2
  '*' → prevOp was '+', push 2.    stack: [3, 2].  prevOp='*'
  '2' → num=2
  '-' → prevOp was '*', pop 2*2=4. stack: [3, 4].  prevOp='-'
  '1' → num=1
  END → prevOp was '-', push -1.   stack: [3, 4, -1]
  
  Sum stack: 3 + 4 + (-1) = 6 ✓
```

### Key Insight
- `+` and `-`: just push (with sign) onto stack
- `*` and `/`: immediately resolve with stack top (higher precedence)
- Final answer: sum everything on stack

### Complexity
- Time: O(n)
- Space: O(n) — stack holds terms between +/-

---

## Pattern 3: Expression Evaluation — With Parentheses

### Signal
- `(` and `)` change evaluation order
- Need to "pause" current context, evaluate inner, resume

### Template (Java)

```java
// LC 224: Basic Calculator — has +, -, (, )
public int calculate(String s) {
    Deque<Integer> stack = new ArrayDeque<>();
    int result = 0;
    int num = 0;
    int sign = 1;
    
    for (int i = 0; i < s.length(); i++) {
        char c = s.charAt(i);
        if (Character.isDigit(c)) {
            num = num * 10 + (c - '0');
        } else if (c == '+') {
            result += sign * num;
            num = 0;
            sign = 1;
        } else if (c == '-') {
            result += sign * num;
            num = 0;
            sign = -1;
        } else if (c == '(') {
            // Save context: current result and sign
            stack.push(result);
            stack.push(sign);
            // Reset for sub-expression
            result = 0;
            sign = 1;
        } else if (c == ')') {
            result += sign * num;
            num = 0;
            // Restore context
            result *= stack.pop(); // saved sign
            result += stack.pop(); // saved result
        }
    }
    return result + sign * num;
}

// LC 772: Basic Calculator III — +,-,*,/,( )
// Use recursive approach with global index
int i = 0;
public int calculateIII(String s) {
    Deque<Integer> stack = new ArrayDeque<>();
    int num = 0;
    char prevOp = '+';
    
    while (i < s.length()) {
        char c = s.charAt(i);
        i++;
        
        if (Character.isDigit(c)) {
            num = num * 10 + (c - '0');
        } else if (c == '(') {
            num = calculateIII(s); // recurse, returns value of sub-expr
        }
        
        if (c == '+' || c == '-' || c == '*' || c == '/' || c == ')' || i == s.length()) {
            switch (prevOp) {
                case '+': stack.push(num); break;
                case '-': stack.push(-num); break;
                case '*': stack.push(stack.pop() * num); break;
                case '/': stack.push(stack.pop() / num); break;
            }
            prevOp = c;
            num = 0;
            if (c == ')') break; // return to caller
        }
    }
    
    int result = 0;
    for (int val : stack) result += val;
    return result;
}
```

### Visualization

```
Input: "2 * (3 + 1)"

Recursive approach (Calculator III):
  prevOp='+', process '2' → num=2
  '*' → push 2 (prevOp was '+'), prevOp='*'
  '(' → recurse into sub-expression
      │  prevOp='+', process '3' → num=3
      │  '+' → push 3, prevOp='+'
      │  '1' → num=1
      │  ')' → push 1, sum stack=4, return 4
      └─ num = 4
  END → prevOp was '*', pop 2, push 2*4=8
  Sum stack: 8 ✓

Context-save approach (Calculator I):
  "1 - (2 + 3)"
  
  '1'  num=1
  '-'  result=1, sign=-1
  '('  SAVE [result=1, sign=-1] to stack. Reset: result=0, sign=1
  '2'  num=2
  '+'  result=2, sign=1
  '3'  num=3
  ')'  result=2+3=5. RESTORE: 5*(-1)+1 = -4
  
  Answer: -4 ✓
```

### Complexity
- Time: O(n)
- Space: O(depth of nesting) — typically O(n) worst case

---

## Pattern 4: Min Stack / Max Stack

### Signal
- "Design a stack that supports getMin/getMax in O(1)"
- Track extremes alongside normal operations

### Template (Java)

```java
// LC 155: Min Stack
class MinStack {
    private Deque<Integer> stack = new ArrayDeque<>();
    private Deque<Integer> minStack = new ArrayDeque<>();
    
    public void push(int val) {
        stack.push(val);
        // Push to minStack if empty or val <= current min
        if (minStack.isEmpty() || val <= minStack.peek()) {
            minStack.push(val);
        }
    }
    
    public void pop() {
        int val = stack.pop();
        if (val == minStack.peek()) {
            minStack.pop();
        }
    }
    
    public int top() { return stack.peek(); }
    public int getMin() { return minStack.peek(); }
}

// Space-optimized: store (value, minAtThisLevel) pairs
class MinStackSingleStack {
    private Deque<int[]> stack = new ArrayDeque<>(); // [val, currentMin]
    
    public void push(int val) {
        int min = stack.isEmpty() ? val : Math.min(val, stack.peek()[1]);
        stack.push(new int[]{val, min});
    }
    
    public void pop() { stack.pop(); }
    public int top() { return stack.peek()[0]; }
    public int getMin() { return stack.peek()[1]; }
}
```

### Visualization

```
Operations: push(5), push(3), push(7), push(2), pop(), getMin()

Auxiliary stack approach:
  push(5): stack=[5]       minStack=[5]
  push(3): stack=[5,3]     minStack=[5,3]      ← 3<=5, push
  push(7): stack=[5,3,7]   minStack=[5,3]      ← 7>3, skip
  push(2): stack=[5,3,7,2] minStack=[5,3,2]    ← 2<=3, push
  pop():   stack=[5,3,7]   minStack=[5,3]      ← popped 2==min, pop min too
  getMin() → 3 ✓

Pair approach:
  push(5): [(5,5)]
  push(3): [(5,5),(3,3)]
  push(7): [(5,5),(3,3),(7,3)]
  push(2): [(5,5),(3,3),(7,3),(2,2)]
  pop():   [(5,5),(3,3),(7,3)]
  getMin() → peek()[1] = 3 ✓
```

### Variants
| Problem | Twist |
|---------|-------|
| LC 155 Min Stack | Classic auxiliary |
| Max Stack (LC 716) | Also need popMax → use doubly-linked list + TreeMap |
| Max Frequency Stack (LC 895) | Map of freq → stack per frequency level |

### Complexity
- Time: O(1) for all operations
- Space: O(n) auxiliary stack

---

## Pattern 5: Stack for Simulation / Undo

### Signal
- Elements interact: later elements can cancel/modify earlier ones
- Process sequentially, "undo" or "cancel" based on rules
- Asteroid collision, backspace editing, score tracking

### Template (Java)

```java
// LC 735: Asteroid Collision
public int[] asteroidCollision(int[] asteroids) {
    Deque<Integer> stack = new ArrayDeque<>();
    for (int a : asteroids) {
        boolean alive = true;
        // Collision only when stack top goes right (+) and current goes left (-)
        while (alive && a < 0 && !stack.isEmpty() && stack.peek() > 0) {
            if (stack.peek() < -a) {
                stack.pop(); // top destroyed, keep checking
            } else if (stack.peek() == -a) {
                stack.pop(); // both destroyed
                alive = false;
            } else {
                alive = false; // current destroyed
            }
        }
        if (alive) stack.push(a);
    }
    int[] res = new int[stack.size()];
    for (int i = res.length - 1; i >= 0; i--) res[i] = stack.pop();
    return res;
}

// LC 844: Backspace String Compare
public boolean backspaceCompare(String s, String t) {
    return build(s).equals(build(t));
}
private String build(String s) {
    Deque<Character> stack = new ArrayDeque<>();
    for (char c : s.toCharArray()) {
        if (c == '#') { if (!stack.isEmpty()) stack.pop(); }
        else stack.push(c);
    }
    return stack.toString();
}

// LC 682: Baseball Game
public int calPoints(String[] ops) {
    Deque<Integer> stack = new ArrayDeque<>();
    for (String op : ops) {
        switch (op) {
            case "+": 
                int top = stack.pop();
                int newTop = top + stack.peek();
                stack.push(top);
                stack.push(newTop);
                break;
            case "D": stack.push(2 * stack.peek()); break;
            case "C": stack.pop(); break;
            default: stack.push(Integer.parseInt(op));
        }
    }
    int sum = 0;
    for (int val : stack) sum += val;
    return sum;
}
```

### Visualization

```
Asteroid Collision: [5, 10, -5]

  5  → stack: [5]       (going right)
  10 → stack: [5, 10]   (going right)
  -5 → collision with 10: |10| > |-5|, -5 destroyed
       stack: [5, 10]
  
  Output: [5, 10]

Asteroid Collision: [8, -8]
  8  → stack: [8]
  -8 → collision: |8| == |-8|, both destroyed
       stack: []
  Output: []
```

### Complexity
- Time: O(n) — each element pushed/popped at most once
- Space: O(n)

---

## Pattern 6: Decode Nested Strings

### Signal
- Nested encoding: `k[encoded_string]`
- Need to remember outer context when entering `[`
- `3[a2[c]]` → `accaccacc`

### Template (Java)

```java
// LC 394: Decode String
public String decodeString(String s) {
    Deque<StringBuilder> strStack = new ArrayDeque<>();
    Deque<Integer> countStack = new ArrayDeque<>();
    StringBuilder current = new StringBuilder();
    int k = 0;
    
    for (char c : s.toCharArray()) {
        if (Character.isDigit(c)) {
            k = k * 10 + (c - '0');
        } else if (c == '[') {
            // Save context
            countStack.push(k);
            strStack.push(current);
            // Reset
            current = new StringBuilder();
            k = 0;
        } else if (c == ']') {
            // Build repeated string
            StringBuilder decoded = strStack.pop();
            int repeat = countStack.pop();
            for (int i = 0; i < repeat; i++) {
                decoded.append(current);
            }
            current = decoded;
        } else {
            current.append(c);
        }
    }
    return current.toString();
}
```

### Visualization

```
Input: "3[a2[c]]"

Processing character by character:
  '3' → k=3
  '[' → SAVE context: countStack=[3], strStack=[""]
         Reset: current="", k=0
  'a' → current="a"
  '2' → k=2
  '[' → SAVE context: countStack=[3,2], strStack=["","a"]
         Reset: current="", k=0
  'c' → current="c"
  ']' → POP: repeat=2, outer="a"
         decoded = "a" + "c"*2 = "acc"
         current="acc"
         countStack=[3], strStack=[""]
  ']' → POP: repeat=3, outer=""
         decoded = "" + "acc"*3 = "accaccacc"
         current="accaccacc"

Output: "accaccacc" ✓
```

### Key Insight
The stack stores **context** (what came before the `[`), not the inner content. On `]`, we restore the outer context and append the repeated inner result.

### Complexity
- Time: O(n * maxRepeat) — output length
- Space: O(depth of nesting) for stacks

---

## Pattern 7: Remove K Digits / Build Optimal Number

### Signal
- "Remove k digits to make smallest number"
- Build optimal sequence greedily: remove larger preceding digits
- Stack maintains increasing (or desired) order from bottom to top

### Template (Java)

```java
// LC 402: Remove K Digits
public String removeKdigits(String num, int k) {
    Deque<Character> stack = new ArrayDeque<>();
    
    for (char c : num.toCharArray()) {
        // Remove previous larger digits while we still have removals left
        while (k > 0 && !stack.isEmpty() && stack.peek() > c) {
            stack.pop();
            k--;
        }
        stack.push(c);
    }
    
    // If k remaining, remove from end (largest at top won't happen if ascending)
    while (k > 0) {
        stack.pop();
        k--;
    }
    
    // Build result, strip leading zeros
    StringBuilder sb = new StringBuilder();
    while (!stack.isEmpty()) sb.append(stack.pollLast());
    while (sb.length() > 0 && sb.charAt(0) == '0') sb.deleteCharAt(0);
    
    return sb.length() == 0 ? "0" : sb.toString();
}
```

### Visualization

```
Input: num = "1432219", k = 3

  '1' → stack: [1]
  '4' → 4>1? no pop. stack: [1,4]
  '3' → 3<4, pop 4 (k=2). stack: [1,3]
  '2' → 2<3, pop 3 (k=1). stack: [1,2]
  '2' → 2≤2, no pop. stack: [1,2,2]
  '1' → 1<2, pop 2 (k=0). stack: [1,2,1]
  '9' → k=0, just push. stack: [1,2,1,9]
  
  Result: "1219" ✓
  
  Greedy principle: 
  For leftmost position, we want smallest possible digit.
  Popping a larger digit when a smaller one follows → smaller number.
```

### Variants
| Problem | Twist |
|---------|-------|
| LC 402 Remove K Digits | Minimize number |
| LC 321 Create Maximum Number | Maximize, from two arrays |
| LC 1673 Most Competitive Subsequence | Same pattern, keep n-k elements |

### Complexity
- Time: O(n) — each digit pushed/popped at most once
- Space: O(n)

---

## Pattern 8: Remove Duplicate Letters (Smallest Subsequence)

### Signal
- Remove duplicates, keep one of each character
- Result must be **lexicographically smallest**
- Relative order preserved

### Template (Java)

```java
// LC 316 / LC 1081: Remove Duplicate Letters
public String removeDuplicateLetters(String s) {
    int[] freq = new int[26];        // remaining frequency
    boolean[] inStack = new boolean[26]; // is char already in result?
    Deque<Character> stack = new ArrayDeque<>();
    
    for (char c : s.toCharArray()) freq[c - 'a']++;
    
    for (char c : s.toCharArray()) {
        freq[c - 'a']--; // consume one occurrence
        
        if (inStack[c - 'a']) continue; // already placed
        
        // Pop stack top if:
        // 1. current char is smaller (lexicographic improvement)
        // 2. stack top char appears later (safe to remove now)
        while (!stack.isEmpty() && c < stack.peek() && freq[stack.peek() - 'a'] > 0) {
            inStack[stack.pop() - 'a'] = false;
        }
        
        stack.push(c);
        inStack[c - 'a'] = true;
    }
    
    StringBuilder sb = new StringBuilder();
    while (!stack.isEmpty()) sb.append(stack.pollLast());
    return sb.toString();
}
```

### Visualization

```
Input: "cbacdcbc"
freq initially: a=1, b=2, c=4, d=1

  'c' freq[c]=3. stack empty, push. stack:[c] inStack:{c}
  'b' freq[b]=1. b<c, freq[c]=3>0 → pop c. stack:[b] inStack:{b}
  'a' freq[a]=0. a<b, freq[b]=1>0 → pop b. stack:[a] inStack:{a}
  'c' freq[c]=2. c>a, push. stack:[a,c] inStack:{a,c}
  'd' freq[d]=0. d>c, push. stack:[a,c,d] inStack:{a,c,d}
  'c' freq[c]=1. c already inStack → skip
  'b' freq[b]=0. b<d but freq[d]=0 → can't pop d. push. stack:[a,c,d,b]
  'c' freq[c]=0. c already inStack → skip
  
  Result: "acdb" ✓

Three conditions to pop:
  ┌─────────────────────────────────────────────┐
  │ 1. Current char < stack top  (improvement)  │
  │ 2. Stack top appears later   (safe to pop)  │
  │ 3. Current char not already in stack         │
  └─────────────────────────────────────────────┘
```

### Complexity
- Time: O(n) — each char pushed/popped at most once
- Space: O(26) = O(1) for the boolean/freq arrays, O(n) for stack

---

## Summary Comparison

| # | Pattern | Stack Contains | Pop Condition |
|---|---------|---------------|---------------|
| 1 | Bracket Match | Expected closers or indices | Matching closer found |
| 2 | Expr (no parens) | Resolved +/- terms | `*`/`/` resolves immediately |
| 3 | Expr (parens) | Saved context (result+sign) | `)` triggers restore |
| 4 | Min/Max Stack | Auxiliary extremes | Mirrors main pop |
| 5 | Simulation/Undo | Active elements | Collision/cancel rules |
| 6 | Decode Nested | Outer string + repeat count | `]` triggers build |
| 7 | Remove K Digits | Increasing digits (optimal) | Current < top AND k > 0 |
| 8 | Remove Dup Letters | Unique sorted chars | Current < top AND top appears later |

---

## Common Pitfalls

1. **Using `Stack<>` class** — Use `Deque<> = new ArrayDeque<>()`. Java's `Stack` is synchronized/legacy.
2. **Forgetting end-of-string** — Expression evaluation must process the last number when loop ends.
3. **Leading zeros** — Pattern 7 requires stripping after building result.
4. **`<=` vs `<` in MinStack** — Must push to minStack on `<=` (duplicates matter for pop correctness).
5. **Asteroid direction** — Collision only when `top > 0 && current < 0`. Same direction = no collision.
