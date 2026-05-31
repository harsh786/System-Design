# 30 - Recursion & Tree Recursion Patterns

## Decision Flowchart: Which Tree Pattern to Use

```
Is the problem about a tree/recursive structure?
│
├─ YES: Do you need info from parent/ancestors?
│   ├─ YES → Top-Down (pass via parameters)
│   └─ NO: Do you need info from children/subtrees?
│       ├─ YES: Is the answer at a single node or across nodes?
│       │   ├─ Single node → Bottom-Up (return values up)
│       │   └─ Across nodes (path through root) → Path Pattern (global + local)
│       └─ NO → Simple traversal
│
├─ Is it BST-specific?
│   └─ YES → Use BST property (left < root < right)
│
├─ Is it construction?
│   └─ YES → Divide input, recurse on halves
│
└─ Need O(1) space traversal?
    └─ YES → Morris Traversal
```

---

## 1. Linear Recursion

### Signal
- Problem decomposes into **one** smaller subproblem of same type
- Base case is trivially solvable
- Each call does O(1) work + one recursive call

### Template (Java)

```java
// General Linear Recursion Template
ReturnType solve(Input input) {
    // Base case
    if (isBaseCase(input)) return baseCaseResult;
    
    // Decompose: reduce problem size by 1 (or constant)
    // Recurse on smaller subproblem
    ReturnType subResult = solve(smaller(input));
    
    // Combine: merge subResult with current level's work
    return combine(input, subResult);
}
```

#### Factorial

```java
int factorial(int n) {
    if (n <= 1) return 1;           // Base case
    return n * factorial(n - 1);     // n * (n-1)!
}
```

#### Power (Fast Exponentiation)

```java
// O(log n) - reduces to half each time
double power(double base, int exp) {
    if (exp == 0) return 1.0;
    if (exp < 0) return 1.0 / power(base, -exp);
    
    double half = power(base, exp / 2);
    if (exp % 2 == 0) return half * half;
    else return half * half * base;
}
```

#### String Reversal

```java
String reverse(String s, int lo, int hi) {
    if (lo >= hi) return s;
    char[] arr = s.toCharArray();
    char tmp = arr[lo]; arr[lo] = arr[hi]; arr[hi] = tmp;
    return reverse(new String(arr), lo + 1, hi - 1);
}
```

### Call Stack Visualization

```
factorial(4)
│ stack frame: n=4, waiting for factorial(3)
├── factorial(3)
│   │ stack frame: n=3, waiting for factorial(2)
│   ├── factorial(2)
│   │   │ stack frame: n=2, waiting for factorial(1)
│   │   ├── factorial(1)
│   │   │   returns 1          ← base case hit
│   │   returns 2 * 1 = 2     ← unwind
│   returns 3 * 2 = 6         ← unwind
returns 4 * 6 = 24            ← unwind

Stack depth at max: [main] → [f(4)] → [f(3)] → [f(2)] → [f(1)]
                     O(n) space
```

### Complexity

| Problem | Time | Space | Recurrence |
|---------|------|-------|------------|
| Factorial | O(n) | O(n) | T(n) = T(n-1) + O(1) |
| Power | O(log n) | O(log n) | T(n) = T(n/2) + O(1) |
| String Reverse | O(n) | O(n) | T(n) = T(n-2) + O(1) |

---

## 2. Binary / Tree Recursion

### Signal
- Problem decomposes into **two or more** subproblems
- Often: split input in half, or recurse on left and right children
- Exponential naive solutions often optimizable via memoization

### Template (Java)

```java
ReturnType solve(Input input) {
    if (isBaseCase(input)) return baseCaseResult;
    
    ReturnType left = solve(leftHalf(input));
    ReturnType right = solve(rightHalf(input));
    
    return combine(left, right, input);
}
```

#### Fibonacci (Naive → Memoized)

```java
// Naive: O(2^n) time, O(n) space
int fib(int n) {
    if (n <= 1) return n;
    return fib(n - 1) + fib(n - 2);
}

// Memoized: O(n) time, O(n) space
int fib(int n, int[] memo) {
    if (n <= 1) return n;
    if (memo[n] != 0) return memo[n];
    memo[n] = fib(n - 1, memo) + fib(n - 2, memo);
    return memo[n];
}
```

#### Binary Tree Traversals

```java
// Inorder: Left → Root → Right
void inorder(TreeNode root, List<Integer> result) {
    if (root == null) return;
    inorder(root.left, result);
    result.add(root.val);
    inorder(root.right, result);
}

// Preorder: Root → Left → Right
void preorder(TreeNode root, List<Integer> result) {
    if (root == null) return;
    result.add(root.val);
    preorder(root.left, result);
    preorder(root.right, result);
}

// Postorder: Left → Right → Root
void postorder(TreeNode root, List<Integer> result) {
    if (root == null) return;
    postorder(root.left, result);
    postorder(root.right, result);
    result.add(root.val);
}
```

### Visualization: Fibonacci Call Tree

```
                    fib(5)
                   /      \
              fib(4)       fib(3)
             /     \       /     \
         fib(3)  fib(2)  fib(2)  fib(1)
         /   \    / \     / \
     fib(2) fib(1) ...  ...
      / \
  fib(1) fib(0)

Calls without memo: 2^n (exponential)
Calls with memo:    2n-1 (linear) - each fib(k) computed once
```

### Complexity

| Problem | Time | Space | Recurrence |
|---------|------|-------|------------|
| Fibonacci (naive) | O(2^n) | O(n) | T(n) = T(n-1) + T(n-2) + O(1) |
| Fibonacci (memo) | O(n) | O(n) | Each subproblem solved once |
| Tree traversal | O(n) | O(h) | T(n) = T(k) + T(n-k-1) + O(1) |

---

## 3. Tree DFS Patterns

### 3a. Top-Down (Pass Info Down via Parameters)

#### Signal
- You need depth, path sum so far, parent value, or any ancestor information
- Information flows **root → leaves**
- Often uses a helper with extra parameters

#### Template

```java
void topDown(TreeNode node, State parentState) {
    if (node == null) return;
    
    // Use parentState + current node to compute something
    State currentState = compute(parentState, node);
    
    // Optionally update answer at this node
    if (isLeaf(node)) updateAnswer(currentState);
    
    // Pass state down to children
    topDown(node.left, currentState);
    topDown(node.right, currentState);
}
```

#### Example: Max Depth (Top-Down)

```java
int answer = 0;

void maxDepth(TreeNode node, int depth) {
    if (node == null) return;
    if (node.left == null && node.right == null) {
        answer = Math.max(answer, depth);
    }
    maxDepth(node.left, depth + 1);
    maxDepth(node.right, depth + 1);
}
```

#### Example: Path Sum (Root to Leaf = Target)

```java
boolean hasPathSum(TreeNode node, int remaining) {
    if (node == null) return false;
    remaining -= node.val;
    if (node.left == null && node.right == null) return remaining == 0;
    return hasPathSum(node.left, remaining) || hasPathSum(node.right, remaining);
}
```

### 3b. Bottom-Up (Collect Info from Children, Return Up)

#### Signal
- Answer at a node depends on answers from its subtrees
- Information flows **leaves → root**
- Function **returns** a value that parent uses

#### Template

```java
ReturnType bottomUp(TreeNode node) {
    if (node == null) return baseValue;
    
    ReturnType leftResult = bottomUp(node.left);
    ReturnType rightResult = bottomUp(node.right);
    
    // Combine children results with current node
    return combine(leftResult, rightResult, node);
}
```

#### Example: Max Depth (Bottom-Up)

```java
int maxDepth(TreeNode node) {
    if (node == null) return 0;
    int left = maxDepth(node.left);
    int right = maxDepth(node.right);
    return 1 + Math.max(left, right);
}
```

#### Example: Is Balanced

```java
// Returns height if balanced, -1 if not
int checkBalance(TreeNode node) {
    if (node == null) return 0;
    
    int left = checkBalance(node.left);
    if (left == -1) return -1;  // Early termination
    
    int right = checkBalance(node.right);
    if (right == -1) return -1;
    
    if (Math.abs(left - right) > 1) return -1;
    return 1 + Math.max(left, right);
}
```

### 3c. Path Problems (Global Max + Local Return)

#### Signal
- Answer is a **path** that may pass through any node as the "bend point"
- At each node: best path **through** this node vs best path in subtrees
- Pattern: maintain **global answer** (instance variable) + return **local value** (usable by parent)

#### Template

```java
int globalMax = Integer.MIN_VALUE;

// Returns: best "arm" extending from this node downward (usable by parent)
int dfs(TreeNode node) {
    if (node == null) return 0;
    
    int leftArm = Math.max(0, dfs(node.left));   // 0 = don't take negative path
    int rightArm = Math.max(0, dfs(node.right));
    
    // Path through this node as bend point
    int throughThis = leftArm + node.val + rightArm;
    globalMax = Math.max(globalMax, throughThis);
    
    // Return best single arm to parent
    return node.val + Math.max(leftArm, rightArm);
}
```

#### Visualization: Path Pattern Logic

```
For each node X:
                  [parent]
                     |
                    [X]  ← bend point
                   /   \
             leftArm   rightArm

  "Through X" path = leftArm + X.val + rightArm  → update global
  "Arm from X" to parent = X.val + max(leftArm, rightArm) → return

Key insight: A path can only "bend" once. So we return a straight arm to parent.
```

---

## 4. Binary Tree Construction

### Signal
- Given traversal orders (preorder + inorder, etc.) → reconstruct tree
- Given sorted structure → build balanced BST
- Key: identify root, then partition remaining elements into left/right subtrees

### From Preorder + Inorder (LC 105)

```java
int preIdx = 0;
Map<Integer, Integer> inorderMap = new HashMap<>();

TreeNode buildTree(int[] preorder, int[] inorder) {
    for (int i = 0; i < inorder.length; i++)
        inorderMap.put(inorder[i], i);
    return build(preorder, 0, inorder.length - 1);
}

TreeNode build(int[] preorder, int inLeft, int inRight) {
    if (inLeft > inRight) return null;
    
    int rootVal = preorder[preIdx++];
    TreeNode root = new TreeNode(rootVal);
    
    int inIdx = inorderMap.get(rootVal);  // Root position in inorder
    
    // LEFT subtree first (matches preorder's next elements)
    root.left = build(preorder, inLeft, inIdx - 1);
    root.right = build(preorder, inIdx + 1, inRight);
    
    return root;
}
```

### Visualization: Construction Logic

```
preorder = [3, 9, 20, 15, 7]    inorder = [9, 3, 15, 20, 7]

Step 1: preorder[0] = 3 is root
        inorder split: [9] | 3 | [15, 20, 7]
                       left       right

Step 2: preorder[1] = 9 is left subtree root
        inorder split: [] | 9 | []  → leaf

Step 3: preorder[2] = 20 is right subtree root
        inorder split: [15] | 20 | [7]

Result:       3
             / \
            9   20
               / \
              15   7
```

### Sorted Array to BST (LC 108)

```java
TreeNode sortedArrayToBST(int[] nums) {
    return build(nums, 0, nums.length - 1);
}

TreeNode build(int[] nums, int lo, int hi) {
    if (lo > hi) return null;
    int mid = lo + (hi - lo) / 2;
    TreeNode root = new TreeNode(nums[mid]);
    root.left = build(nums, lo, mid - 1);
    root.right = build(nums, mid + 1, hi);
    return root;
}
```

### Complexity
- Time: O(n) for both (with hashmap for inorder lookup)
- Space: O(n) for hashmap + O(h) recursion stack

---

## 5. BST Operations

### Signal
- Binary Search Tree property: `left.val < node.val < right.val` for all nodes
- Enables O(h) search/insert/delete by choosing one direction

### Search

```java
TreeNode search(TreeNode root, int target) {
    if (root == null || root.val == target) return root;
    if (target < root.val) return search(root.left, target);
    return search(root.right, target);
}
```

### Insert

```java
TreeNode insert(TreeNode root, int val) {
    if (root == null) return new TreeNode(val);
    if (val < root.val) root.left = insert(root.left, val);
    else root.right = insert(root.right, val);
    return root;
}
```

### Delete

```java
TreeNode delete(TreeNode root, int key) {
    if (root == null) return null;
    
    if (key < root.val) root.left = delete(root.left, key);
    else if (key > root.val) root.right = delete(root.right, key);
    else {
        // Found node to delete
        if (root.left == null) return root.right;
        if (root.right == null) return root.left;
        
        // Two children: replace with inorder successor
        TreeNode successor = findMin(root.right);
        root.val = successor.val;
        root.right = delete(root.right, successor.val);
    }
    return root;
}

TreeNode findMin(TreeNode node) {
    while (node.left != null) node = node.left;
    return node;
}
```

### Validate BST (LC 98)

```java
boolean isValidBST(TreeNode root) {
    return validate(root, Long.MIN_VALUE, Long.MAX_VALUE);
}

boolean validate(TreeNode node, long min, long max) {
    if (node == null) return true;
    if (node.val <= min || node.val >= max) return false;
    return validate(node.left, min, node.val) &&
           validate(node.right, node.val, max);
}
```

### BST LCA (LC 235)

```java
// BST property makes this O(h) - no need to search both subtrees
TreeNode lcaBST(TreeNode root, TreeNode p, TreeNode q) {
    if (p.val < root.val && q.val < root.val) return lcaBST(root.left, p, q);
    if (p.val > root.val && q.val > root.val) return lcaBST(root.right, p, q);
    return root;  // Split point = LCA
}
```

### Complexity
All BST ops: O(h) time, O(h) space where h = log n (balanced) or n (skewed)

---

## 6. Lowest Common Ancestor (Binary Tree - Postorder)

### Signal
- Find the deepest node that is ancestor of both p and q
- Must check both subtrees (not BST, can't use value comparison)
- **Postorder** pattern: get info from children first, then decide at current node

### Template (LC 236)

```java
TreeNode lowestCommonAncestor(TreeNode root, TreeNode p, TreeNode q) {
    // Base cases
    if (root == null) return null;
    if (root == p || root == q) return root;
    
    // Postorder: search both subtrees
    TreeNode left = lowestCommonAncestor(root.left, p, q);
    TreeNode right = lowestCommonAncestor(root.right, p, q);
    
    // If both sides found something, current node is LCA
    if (left != null && right != null) return root;
    
    // Otherwise, LCA is in whichever side found something
    return left != null ? left : right;
}
```

### Visualization

```
         3
        / \
       5   1
      / \ / \
     6  2 0  8
       / \
      7   4

LCA(5, 1):
  - At 3: left finds 5, right finds 1 → both non-null → return 3 ✓

LCA(5, 4):
  - At 3: left finds 5 (because 5==p, returns immediately before reaching 4)
    Wait - that's wrong! Let's trace carefully:
  - At 3: recurse left(5) and right(1)
    - At 5: root==p → return 5 immediately
    - At 1: recurse left(0) right(8) → both null → return null
  - At 3: left=5, right=null → return 5
  
  This works because if 5 is ancestor of 4, returning 5 IS correct.
  The LCA of 5 and 4 is 5 itself (since 5 is ancestor of 4).
```

### Complexity
- Time: O(n) - visit every node in worst case
- Space: O(h) - recursion stack

---

## 7. Serialize / Deserialize Binary Tree (LC 297)

### Signal
- Convert tree to string and back
- Must encode structure (nulls) to enable unique reconstruction
- Preorder with null markers is simplest

### Template

```java
public class Codec {
    
    // Serialize: preorder with "null" markers
    public String serialize(TreeNode root) {
        StringBuilder sb = new StringBuilder();
        serializeHelper(root, sb);
        return sb.toString();
    }
    
    private void serializeHelper(TreeNode node, StringBuilder sb) {
        if (node == null) {
            sb.append("null,");
            return;
        }
        sb.append(node.val).append(",");
        serializeHelper(node.left, sb);
        serializeHelper(node.right, sb);
    }
    
    // Deserialize: consume tokens in preorder sequence
    public TreeNode deserialize(String data) {
        Queue<String> queue = new LinkedList<>(Arrays.asList(data.split(",")));
        return deserializeHelper(queue);
    }
    
    private TreeNode deserializeHelper(Queue<String> queue) {
        String val = queue.poll();
        if ("null".equals(val)) return null;
        
        TreeNode node = new TreeNode(Integer.parseInt(val));
        node.left = deserializeHelper(queue);
        node.right = deserializeHelper(queue);
        return node;
    }
}
```

### Visualization

```
Tree:     1
         / \
        2   3
           / \
          4   5

Serialized (preorder): "1,2,null,null,3,4,null,null,5,null,null,"

Deserialization trace:
  poll "1" → create node(1)
    poll "2" → create node(2)
      poll "null" → left = null
      poll "null" → right = null
    poll "3" → create node(3)
      poll "4" → create node(4)
        poll "null" → left = null
        poll "null" → right = null
      poll "5" → create node(5)
        poll "null" → left = null
        poll "null" → right = null
```

### Complexity
- Time: O(n) serialize + O(n) deserialize
- Space: O(n) for the string representation

---

## 8. Flatten Binary Tree to Linked List (LC 114)

### Signal
- Convert tree to right-skewed linked list **in-place** following preorder
- Key insight: process right-to-left (reverse preorder: right → left → root)

### Template

```java
// Approach 1: Reverse postorder with prev pointer
TreeNode prev = null;

void flatten(TreeNode root) {
    if (root == null) return;
    flatten(root.right);    // Process right first
    flatten(root.left);     // Then left
    root.right = prev;      // Point right to previously processed node
    root.left = null;
    prev = root;
}

// Approach 2: Iterative (Morris-like)
void flattenIterative(TreeNode root) {
    TreeNode curr = root;
    while (curr != null) {
        if (curr.left != null) {
            // Find rightmost node in left subtree
            TreeNode rightmost = curr.left;
            while (rightmost.right != null) rightmost = rightmost.right;
            
            // Rewire
            rightmost.right = curr.right;
            curr.right = curr.left;
            curr.left = null;
        }
        curr = curr.right;
    }
}
```

### Visualization

```
     1              1              1
    / \              \              \
   2   5    →        2      →      2
  / \   \            \              \
 3   4   6            3              3
                       \              \
                        4              4
                         \              \
                          5              5
                           \              \
                            6              6
```

---

## 9. Binary Tree Maximum Path Sum (LC 124)

### Signal
- Path can start and end at **any** node
- At each node, path can go: left arm + node + right arm
- Classic **global max + local return** pattern

### Template

```java
int maxSum = Integer.MIN_VALUE;

int maxPathSum(TreeNode root) {
    dfs(root);
    return maxSum;
}

// Returns: max "gain" this node can contribute to its parent's path
int dfs(TreeNode node) {
    if (node == null) return 0;
    
    // Max gain from left/right child (take 0 if negative = don't take that path)
    int leftGain = Math.max(0, dfs(node.left));
    int rightGain = Math.max(0, dfs(node.right));
    
    // Price of path passing through this node as highest point
    int pathThroughNode = node.val + leftGain + rightGain;
    maxSum = Math.max(maxSum, pathThroughNode);
    
    // Return max gain if continuing through this node (can only go one direction)
    return node.val + Math.max(leftGain, rightGain);
}
```

### Visualization

```
        -10
        /  \
       9    20
           /  \
          15    7

At node 15: leftGain=0, rightGain=0, through=15, return 15
At node 7:  leftGain=0, rightGain=0, through=7, return 7
At node 20: leftGain=15, rightGain=7, through=20+15+7=42 ← GLOBAL MAX
            return 20+max(15,7)=35
At node 9:  through=9, return 9
At node -10: leftGain=9, rightGain=35, through=-10+9+35=34
             return -10+35=25

Answer: 42 (path: 15 → 20 → 7)
```

### Diameter of Binary Tree (LC 543) - Same Pattern

```java
int diameter = 0;

int diameterOfBinaryTree(TreeNode root) {
    depth(root);
    return diameter;
}

int depth(TreeNode node) {
    if (node == null) return 0;
    int left = depth(node.left);
    int right = depth(node.right);
    diameter = Math.max(diameter, left + right);  // Edges through this node
    return 1 + Math.max(left, right);
}
```

---

## 10. Tree Isomorphism / Subtree Check

### Signal
- Compare two tree structures
- Same Tree: identical structure + values
- Subtree: one tree appears as a subtree of another
- Isomorphism: same structure, possibly with left/right children swapped

### Same Tree (LC 100)

```java
boolean isSameTree(TreeNode p, TreeNode q) {
    if (p == null && q == null) return true;
    if (p == null || q == null) return false;
    return p.val == q.val &&
           isSameTree(p.left, q.left) &&
           isSameTree(p.right, q.right);
}
```

### Subtree of Another Tree (LC 572)

```java
boolean isSubtree(TreeNode root, TreeNode subRoot) {
    if (root == null) return false;
    if (isSameTree(root, subRoot)) return true;
    return isSubtree(root.left, subRoot) || isSubtree(root.right, subRoot);
}
// Time: O(m * n) worst case, where m = nodes in root, n = nodes in subRoot
```

### Symmetric Tree (LC 101)

```java
boolean isSymmetric(TreeNode root) {
    return isMirror(root.left, root.right);
}

boolean isMirror(TreeNode a, TreeNode b) {
    if (a == null && b == null) return true;
    if (a == null || b == null) return false;
    return a.val == b.val &&
           isMirror(a.left, b.right) &&
           isMirror(a.right, b.left);
}
```

### Tree Isomorphism (Can Swap Children)

```java
boolean isIsomorphic(TreeNode a, TreeNode b) {
    if (a == null && b == null) return true;
    if (a == null || b == null) return false;
    if (a.val != b.val) return false;
    
    // Either same orientation OR swapped children
    return (isIsomorphic(a.left, b.left) && isIsomorphic(a.right, b.right)) ||
           (isIsomorphic(a.left, b.right) && isIsomorphic(a.right, b.left));
}
```

---

## 11. Morris Traversal (O(1) Space Inorder)

### Signal
- Need inorder traversal with O(1) extra space (no stack, no recursion)
- Temporarily modifies tree structure (creates/removes threaded links)
- Must restore tree to original structure

### Template

```java
List<Integer> morrisInorder(TreeNode root) {
    List<Integer> result = new ArrayList<>();
    TreeNode curr = root;
    
    while (curr != null) {
        if (curr.left == null) {
            // No left subtree: visit and go right
            result.add(curr.val);
            curr = curr.right;
        } else {
            // Find inorder predecessor (rightmost in left subtree)
            TreeNode pred = curr.left;
            while (pred.right != null && pred.right != curr) {
                pred = pred.right;
            }
            
            if (pred.right == null) {
                // First visit: create thread back to curr
                pred.right = curr;
                curr = curr.left;
            } else {
                // Second visit: thread exists, remove it, visit curr
                pred.right = null;
                result.add(curr.val);
                curr = curr.right;
            }
        }
    }
    return result;
}
```

### Visualization

```
Original:       4
               / \
              2   6
             / \
            1   3

Step 1: curr=4, left exists. Predecessor of 4 = 3 (rightmost in left)
        3.right = null → create thread: 3.right = 4. Go left.
        
Step 2: curr=2, left exists. Predecessor of 2 = 1
        1.right = null → create thread: 1.right = 2. Go left.

Step 3: curr=1, no left → VISIT(1), go right (thread) → curr=2

Step 4: curr=2, left exists. Predecessor: 1.right == curr (thread found!)
        Remove thread: 1.right = null. VISIT(2). Go right → curr=3

Step 5: curr=3, no left → VISIT(3), go right (thread) → curr=4

Step 6: curr=4, left exists. Predecessor: 3.right == curr (thread found!)
        Remove thread: 3.right = null. VISIT(4). Go right → curr=6

Step 7: curr=6, no left → VISIT(6). Go right → null. Done.

Result: [1, 2, 3, 4, 6]
```

### Morris Preorder (Small Modification)

```java
// Only change: visit curr when CREATING the thread (first visit)
if (pred.right == null) {
    result.add(curr.val);  // Visit here for preorder
    pred.right = curr;
    curr = curr.left;
} else {
    pred.right = null;
    // DON'T visit here for preorder
    curr = curr.right;
}
```

### Complexity
- Time: O(n) - each edge traversed at most 3 times
- Space: O(1) - no stack, no recursion (excluding output list)

---

## 12. Tail Recursion Optimization

### Signal
- Recursive call is the **last** operation in the function
- No work done after the recursive call returns
- Can be converted to iteration (loop) → O(1) stack space
- Java/Python don't optimize tail calls, but you can manually convert

### Identifying Tail Recursion

```java
// TAIL recursive (last action is the recursive call)
int factorialTail(int n, int acc) {
    if (n <= 1) return acc;
    return factorialTail(n - 1, n * acc);  // Nothing after this call
}

// NOT tail recursive (multiplication happens AFTER recursive call returns)
int factorial(int n) {
    if (n <= 1) return 1;
    return n * factorial(n - 1);  // Must multiply after call returns
}
```

### Conversion to Iteration

```java
// Tail recursive version
int gcd(int a, int b) {
    if (b == 0) return a;
    return gcd(b, a % b);
}

// Iterative equivalent
int gcdIterative(int a, int b) {
    while (b != 0) {
        int temp = b;
        b = a % b;
        a = temp;
    }
    return a;
}
```

### Converting Non-Tail to Tail Recursion (Accumulator Pattern)

```java
// Original: not tail recursive
int sum(int n) {
    if (n == 0) return 0;
    return n + sum(n - 1);  // addition after call
}

// Converted: tail recursive with accumulator
int sumTail(int n, int acc) {
    if (n == 0) return acc;
    return sumTail(n - 1, acc + n);  // nothing after call
}
// Call: sumTail(n, 0)
```

---

## Recursion to Iteration Conversion Patterns

### Pattern 1: Simple Recursion → Loop

```java
// Recursion
void printList(ListNode head) {
    if (head == null) return;
    System.out.println(head.val);
    printList(head.next);
}

// Iteration
void printListIter(ListNode head) {
    while (head != null) {
        System.out.println(head.val);
        head = head.next;
    }
}
```

### Pattern 2: Tree Recursion → Explicit Stack

```java
// Recursive inorder
void inorder(TreeNode root) {
    if (root == null) return;
    inorder(root.left);
    visit(root);
    inorder(root.right);
}

// Iterative inorder with explicit stack
void inorderIterative(TreeNode root) {
    Deque<TreeNode> stack = new ArrayDeque<>();
    TreeNode curr = root;
    
    while (curr != null || !stack.isEmpty()) {
        // Push all left children
        while (curr != null) {
            stack.push(curr);
            curr = curr.left;
        }
        // Visit
        curr = stack.pop();
        visit(curr);
        // Go right
        curr = curr.right;
    }
}
```

### Pattern 3: Preorder → Stack (Simplest)

```java
void preorderIterative(TreeNode root) {
    if (root == null) return;
    Deque<TreeNode> stack = new ArrayDeque<>();
    stack.push(root);
    
    while (!stack.isEmpty()) {
        TreeNode node = stack.pop();
        visit(node);
        if (node.right != null) stack.push(node.right);  // Right first (LIFO)
        if (node.left != null) stack.push(node.left);
    }
}
```

### Pattern 4: Postorder → Two Stacks or Flag

```java
void postorderIterative(TreeNode root) {
    if (root == null) return;
    Deque<TreeNode> stack = new ArrayDeque<>();
    TreeNode curr = root, lastVisited = null;
    
    while (curr != null || !stack.isEmpty()) {
        while (curr != null) {
            stack.push(curr);
            curr = curr.left;
        }
        TreeNode peek = stack.peek();
        if (peek.right != null && peek.right != lastVisited) {
            curr = peek.right;
        } else {
            visit(peek);
            lastVisited = stack.pop();
        }
    }
}
```

---

## Stack Overflow Prevention Techniques

| Technique | When to Use | How |
|-----------|-------------|-----|
| Iterative conversion | Always possible | Replace recursion with explicit stack |
| Tail call elimination | Last action is recursive call | Convert to loop with accumulators |
| Increase stack size | Quick fix, not production | `java -Xss4m` or new Thread with stack size |
| Memoization | Overlapping subproblems | Cache results, prune repeated branches |
| Iterative deepening | Unknown depth, DFS needed | DFS with increasing depth limit |
| Trampoline pattern | Mutual recursion | Return thunks, loop to evaluate |

### Trampoline Pattern (Java)

```java
@FunctionalInterface
interface Thunk<T> {
    Either<Thunk<T>, T> apply();
}

static <T> T trampoline(Thunk<T> thunk) {
    Either<Thunk<T>, T> result = thunk.apply();
    while (result.isLeft()) {
        result = result.getLeft().apply();
    }
    return result.getRight();
}
```

---

## Time Complexity Analysis with Recurrence Relations

### Master Theorem Quick Reference

For `T(n) = aT(n/b) + O(n^d)`:

| Case | Condition | Result |
|------|-----------|--------|
| 1 | d < log_b(a) | O(n^(log_b(a))) |
| 2 | d = log_b(a) | O(n^d * log n) |
| 3 | d > log_b(a) | O(n^d) |

### Common Recurrences in This Guide

| Pattern | Recurrence | Solution |
|---------|-----------|----------|
| Linear recursion | T(n) = T(n-1) + O(1) | O(n) |
| Binary search | T(n) = T(n/2) + O(1) | O(log n) |
| Tree traversal | T(n) = 2T(n/2) + O(1) | O(n) |
| Merge sort style | T(n) = 2T(n/2) + O(n) | O(n log n) |
| Fibonacci naive | T(n) = T(n-1) + T(n-2) | O(2^n) |
| Power (fast) | T(n) = T(n/2) + O(1) | O(log n) |
| Subtree check | T(n) = T(n-1) + O(m) | O(n*m) |

### Proving O(n) for Tree Traversal

```
T(n) = T(k) + T(n-k-1) + c    where k = left subtree size

By substitution (assuming T(n) = an + b):
  a(k) + b + a(n-k-1) + b + c = an + b
  ak + b + an - ak - a + b + c = an + b
  an + 2b - a + c = an + b
  b = a - c

So T(n) = O(n) regardless of tree shape. ∎
```

---

## Summary Cheat Sheet

| Problem Type | Pattern | Key Insight |
|--------------|---------|-------------|
| Need ancestor info | Top-Down | Pass state via parameters |
| Need subtree info | Bottom-Up | Return values to parent |
| Path through nodes | Global + Local | Global tracks best, local returns arm |
| BST operations | Use ordering | Go left or right, never both |
| LCA (general tree) | Postorder | Both sides non-null = found LCA |
| Construction | Identify root + partition | Preorder[0] = root, inorder splits L/R |
| O(1) space traversal | Morris | Threaded predecessor links |
| Avoid stack overflow | Convert to iteration | Explicit stack mirrors call stack |
