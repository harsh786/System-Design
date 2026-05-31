# Binary Search Tree (BST) Patterns

## Decision Flowchart

```
Problem involves sorted/ordered data in a tree?
├── Need sorted iteration → BST Inorder Traversal
├── Search/Insert/Delete in O(h) → Standard BST ops
├── Need rank/kth/count → Augmented BST (size field)
├── Need guaranteed O(log n) → Balanced BST / TreeMap
├── "Validate" or "recover" → Inorder invariant check
├── Two nodes relationship → LCA using BST property
├── Range query [lo, hi] → Trim / Range search
└── Convert sorted ↔ BST → Mid-as-root recursion
```

## BST vs Balanced BST vs TreeMap Decision

| Scenario | Choice | Why |
|----------|--------|-----|
| Interview: implement from scratch | Plain BST | Simple, shows understanding |
| Interview: use as black box | TreeMap/TreeSet | O(log n) guaranteed |
| Design interview: explain tradeoffs | Mention AVL/RB-Tree | Shows depth |
| Skewed input possible | Balanced BST or randomize | Avoid O(n) degradation |

---

## Pattern 1: BST Property & Inorder Invariant

### Signal
- "Binary search tree" in problem statement
- Need sorted sequence from tree
- Verify ordering constraints

### Core Invariant
```
For every node N:
  - All nodes in left subtree < N.val
  - All nodes in right subtree > N.val
  - Inorder traversal yields sorted sequence
```

### Visualization
```
        8
       / \
      3   10
     / \    \
    1   6    14
       / \   /
      4   7 13

Inorder: 1, 3, 4, 6, 7, 8, 10, 13, 14  ← SORTED
```

### Template (Java)
```java
// Inorder traversal - foundation of most BST patterns
void inorder(TreeNode root, List<Integer> result) {
    if (root == null) return;
    inorder(root.left, result);
    result.add(root.val);        // process in sorted order
    inorder(root.right, result);
}
```

### Complexity
- Inorder traversal: O(n) time, O(h) space (recursion stack)

---

## Pattern 2: BST Search

### Signal
- Find a value in BST
- Check existence

### Template (Java)
```java
// Iterative - preferred (no stack overflow risk)
TreeNode search(TreeNode root, int target) {
    while (root != null && root.val != target) {
        root = target < root.val ? root.left : root.right;
    }
    return root;
}

// Recursive
TreeNode searchRec(TreeNode root, int target) {
    if (root == null || root.val == target) return root;
    return target < root.val 
        ? searchRec(root.left, target) 
        : searchRec(root.right, target);
}
```

### Complexity
- Time: O(h) → O(log n) balanced, O(n) skewed
- Space: O(1) iterative, O(h) recursive

---

## Pattern 3: BST Insert

### Signal
- Add element maintaining BST property

### Template (Java)
```java
TreeNode insert(TreeNode root, int val) {
    if (root == null) return new TreeNode(val);
    if (val < root.val)
        root.left = insert(root.left, val);
    else if (val > root.val)
        root.right = insert(root.right, val);
    // val == root.val: duplicate, skip or handle
    return root;
}

// Iterative
TreeNode insertIter(TreeNode root, int val) {
    if (root == null) return new TreeNode(val);
    TreeNode cur = root, parent = null;
    while (cur != null) {
        parent = cur;
        cur = val < cur.val ? cur.left : cur.right;
    }
    if (val < parent.val) parent.left = new TreeNode(val);
    else parent.right = new TreeNode(val);
    return root;
}
```

### Complexity
- Time: O(h), Space: O(h) recursive / O(1) iterative

---

## Pattern 4: BST Delete (3 Cases)

### Signal
- Remove node while maintaining BST property

### Visualization
```
Case 1: Leaf node → just remove
Case 2: One child → replace with child
Case 3: Two children → replace with inorder successor (or predecessor)

Delete 3 from:        Find successor (4):      Result:
      5                     5                     5
     / \                   / \                   / \
    3   8        →        4   8        →        4   8
   / \                   / \                   /   
  2   4                 2   4                 2    
                            ↑ (successor)
```

### Template (Java)
```java
TreeNode delete(TreeNode root, int key) {
    if (root == null) return null;
    
    if (key < root.val) {
        root.left = delete(root.left, key);
    } else if (key > root.val) {
        root.right = delete(root.right, key);
    } else {
        // Found the node to delete
        // Case 1 & 2: leaf or one child
        if (root.left == null) return root.right;
        if (root.right == null) return root.left;
        
        // Case 3: two children - find inorder successor
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

### Complexity
- Time: O(h), Space: O(h)

---

## Pattern 5: Validate BST

### Signal
- "Is this a valid BST?"
- LC 98: Validate Binary Search Tree

### Approach 1: Min/Max Bounds (Preferred)
```java
boolean isValidBST(TreeNode root) {
    return validate(root, Long.MIN_VALUE, Long.MAX_VALUE);
}

boolean validate(TreeNode node, long min, long max) {
    if (node == null) return true;
    if (node.val <= min || node.val >= max) return false;
    return validate(node.left, min, node.val) 
        && validate(node.right, node.val, max);
}
```

### Approach 2: Inorder Must Be Sorted
```java
TreeNode prev = null;

boolean isValidBST(TreeNode root) {
    if (root == null) return true;
    if (!isValidBST(root.left)) return false;
    if (prev != null && root.val <= prev.val) return false;
    prev = root;
    return isValidBST(root.right);
}
```

### Key Insight
- Common mistake: only checking `left.val < node.val < right.val` (ignores subtree constraint)
- Must ensure ALL left subtree < node < ALL right subtree

### Complexity
- Time: O(n), Space: O(h)

---

## Pattern 6: Kth Smallest Element

### Signal
- "Kth smallest/largest in BST"
- LC 230: Kth Smallest Element in a BST

### Approach 1: Inorder with Counter
```java
int count = 0, result = 0;

int kthSmallest(TreeNode root, int k) {
    inorder(root, k);
    return result;
}

void inorder(TreeNode node, int k) {
    if (node == null) return;
    inorder(node.left, k);
    if (++count == k) { result = node.val; return; }
    inorder(node.right, k);
}
```

### Approach 2: Iterative (stops early, cleaner)
```java
int kthSmallest(TreeNode root, int k) {
    Deque<TreeNode> stack = new ArrayDeque<>();
    TreeNode cur = root;
    while (cur != null || !stack.isEmpty()) {
        while (cur != null) {
            stack.push(cur);
            cur = cur.left;
        }
        cur = stack.pop();
        if (--k == 0) return cur.val;
        cur = cur.right;
    }
    return -1; // unreachable if k is valid
}
```

### Approach 3: Augmented BST (for repeated queries)
```java
// Each node stores size of left subtree
// If leftSize == k-1 → current is answer
// If leftSize >= k → go left
// Else → go right with k = k - leftSize - 1
```

### Complexity
- Approaches 1 & 2: O(h + k) time, O(h) space
- Augmented: O(h) time per query after O(n) build

---

## Pattern 7: LCA in BST

### Signal
- "Lowest Common Ancestor" + BST
- LC 235: LCA of a BST

### Key Insight
Unlike general binary tree LCA, exploit BST property:
- Both values < node → LCA is in left subtree
- Both values > node → LCA is in right subtree
- Split point (one left, one right, or one equals node) → current node IS the LCA

### Template (Java)
```java
TreeNode lowestCommonAncestor(TreeNode root, TreeNode p, TreeNode q) {
    while (root != null) {
        if (p.val < root.val && q.val < root.val)
            root = root.left;
        else if (p.val > root.val && q.val > root.val)
            root = root.right;
        else
            return root; // split point
    }
    return null;
}
```

### Complexity
- Time: O(h), Space: O(1)

---

## Pattern 8: Convert Sorted Array/List to Balanced BST

### Signal
- "Sorted array to BST"
- "Sorted linked list to BST"
- LC 108, LC 109

### Key Insight
Middle element becomes root → guarantees balance. Recursively apply to left and right halves.

### Template: Sorted Array (Java)
```java
TreeNode sortedArrayToBST(int[] nums) {
    return build(nums, 0, nums.length - 1);
}

TreeNode build(int[] nums, int lo, int hi) {
    if (lo > hi) return null;
    int mid = lo + (hi - lo) / 2;
    TreeNode node = new TreeNode(nums[mid]);
    node.left = build(nums, lo, mid - 1);
    node.right = build(nums, mid + 1, hi);
    return node;
}
```

### Template: Sorted Linked List (simulate inorder)
```java
ListNode head;

TreeNode sortedListToBST(ListNode h) {
    head = h;
    int n = length(h);
    return build(0, n - 1);
}

TreeNode build(int lo, int hi) {
    if (lo > hi) return null;
    int mid = lo + (hi - lo) / 2;
    TreeNode left = build(lo, mid - 1);
    TreeNode node = new TreeNode(head.val); // inorder position
    node.left = left;
    head = head.next;                       // advance pointer
    node.right = build(mid + 1, hi);
    return node;
}
```

### Complexity
- Time: O(n), Space: O(log n) recursion stack
- Result height: O(log n) guaranteed

---

## Pattern 9: BST Iterator (Controlled Inorder)

### Signal
- "Implement iterator for BST"
- "next() and hasNext() in O(h) space"
- LC 173: Binary Search Tree Iterator

### Template (Java)
```java
class BSTIterator {
    Deque<TreeNode> stack = new ArrayDeque<>();
    
    BSTIterator(TreeNode root) {
        pushLeft(root);
    }
    
    int next() {
        TreeNode node = stack.pop();
        pushLeft(node.right);  // prepare next smallest
        return node.val;
    }
    
    boolean hasNext() {
        return !stack.isEmpty();
    }
    
    private void pushLeft(TreeNode node) {
        while (node != null) {
            stack.push(node);
            node = node.left;
        }
    }
}
```

### Key Insight
This is a "paused" inorder traversal. The stack holds the path to the next node.

### Complexity
- next(): Amortized O(1), worst case O(h)
- Space: O(h)

---

## Pattern 10: Recover BST (Two Swapped Nodes)

### Signal
- "Two nodes swapped by mistake, recover the BST"
- LC 99: Recover Binary Search Tree

### Key Insight
In a correct BST, inorder is strictly increasing. Two swapped nodes create:
- **Adjacent swap**: one violation (prev > cur)
- **Non-adjacent swap**: two violations

```
Correct inorder: 1 2 3 4 5 6 7
Swap 2 and 6:    1 6 3 4 5 2 7
                   ↑ violation1   ↑ violation2
First bad: 6 (first.prev at violation1)
Second bad: 2 (cur at violation2)
```

### Template (Java)
```java
TreeNode first = null, second = null, prev = null;

void recoverTree(TreeNode root) {
    inorder(root);
    // Swap values of first and second
    int tmp = first.val;
    first.val = second.val;
    second.val = tmp;
}

void inorder(TreeNode node) {
    if (node == null) return;
    inorder(node.left);
    if (prev != null && prev.val > node.val) {
        if (first == null) first = prev; // first violation
        second = node;                    // always update second
    }
    prev = node;
    inorder(node.right);
}
```

### Complexity
- Time: O(n), Space: O(h)
- Morris traversal variant: O(1) space

---

## Pattern 11: Trim BST

### Signal
- "Remove all nodes outside range [lo, hi]"
- LC 669: Trim a Binary Search Tree

### Template (Java)
```java
TreeNode trimBST(TreeNode root, int lo, int hi) {
    if (root == null) return null;
    if (root.val < lo) return trimBST(root.right, lo, hi); // discard left subtree
    if (root.val > hi) return trimBST(root.left, lo, hi);  // discard right subtree
    root.left = trimBST(root.left, lo, hi);
    root.right = trimBST(root.right, lo, hi);
    return root;
}
```

### Visualization
```
Trim [2, 8] on:          Result:
        10                    5
       /  \                  / \
      5    15      →        3   7
     / \                     \
    3   7                     4
     \
      4
```

### Complexity
- Time: O(n), Space: O(h)

---

## Pattern 12: Convert BST to Greater Tree

### Signal
- "Replace each node with sum of all greater nodes + itself"
- LC 538 / LC 1038

### Key Insight
Reverse inorder (right → node → left) visits nodes in decreasing order. Maintain running sum.

### Template (Java)
```java
int runningSum = 0;

TreeNode convertBST(TreeNode root) {
    if (root == null) return null;
    convertBST(root.right);         // visit greater nodes first
    runningSum += root.val;
    root.val = runningSum;
    convertBST(root.left);
    return root;
}
```

### Visualization
```
Original:          Greater Tree:
    5                  18
   / \                /  \
  3   8      →      21   8
 / \   \           / \    \
1   4   10       22  19   10
                  (1+3+4+5+8+10=31? No: 
                   node 1: 1+3+4+5+8+10=31... 
                   Actually: each = sum of all >= itself)

Node 10: 10
Node 8: 8+10 = 18
Node 5: 5+8+10 = 23... 

Reverse inorder: 10, 8, 5, 4, 3, 1
Running sum:     10, 18, 23, 27, 30, 31
```

### Complexity
- Time: O(n), Space: O(h)

---

## Pattern 13: Closest BST Value / Closest K Values

### Signal
- "Find closest value to target in BST"
- "Find k closest values to target"
- LC 270, LC 272

### Closest Single Value
```java
int closestValue(TreeNode root, double target) {
    int closest = root.val;
    while (root != null) {
        if (Math.abs(root.val - target) < Math.abs(closest - target))
            closest = root.val;
        root = target < root.val ? root.left : root.right;
    }
    return closest;
}
```

### Closest K Values (Two-Stack Approach)
```java
// Build predecessor stack and successor stack from target
// Then merge like merge-sort picking k closest
List<Integer> closestKValues(TreeNode root, double target, int k) {
    Deque<TreeNode> predStack = new ArrayDeque<>(); // decreasing
    Deque<TreeNode> succStack = new ArrayDeque<>(); // increasing
    
    // Initialize: find target position, build both stacks
    TreeNode cur = root;
    while (cur != null) {
        if (cur.val <= target) {
            predStack.push(cur);
            cur = cur.right;
        } else {
            succStack.push(cur);
            cur = cur.left;
        }
    }
    
    List<Integer> result = new ArrayList<>();
    while (result.size() < k) {
        if (predStack.isEmpty()) {
            result.add(getNextSuccessor(succStack));
        } else if (succStack.isEmpty()) {
            result.add(getNextPredecessor(predStack));
        } else if (target - predStack.peek().val <= succStack.peek().val - target) {
            result.add(getNextPredecessor(predStack));
        } else {
            result.add(getNextSuccessor(succStack));
        }
    }
    return result;
}

int getNextPredecessor(Deque<TreeNode> stack) {
    TreeNode node = stack.pop();
    int val = node.val;
    node = node.left;
    while (node != null) { stack.push(node); node = node.right; }
    return val;
}

int getNextSuccessor(Deque<TreeNode> stack) {
    TreeNode node = stack.pop();
    int val = node.val;
    node = node.right;
    while (node != null) { stack.push(node); node = node.left; }
    return val;
}
```

### Complexity
- Closest single: O(h) time, O(1) space
- Closest K: O(h + k) time, O(h) space

---

## Pattern 14: Count of Smaller Numbers After Self

### Signal
- "For each element, count how many smaller elements come after it"
- LC 315

### Approach: Augmented BST (insert from right, track left subtree size)
```java
class AugNode {
    int val, leftSize = 0, dupCount = 1;
    AugNode left, right;
    AugNode(int v) { val = v; }
}

// Insert from right to left, counting smaller elements
int[] countSmaller(int[] nums) {
    int n = nums.length;
    int[] result = new int[n];
    AugNode root = null;
    
    for (int i = n - 1; i >= 0; i--) {
        root = insert(root, nums[i], result, i, 0);
    }
    return result;
}

AugNode insert(AugNode node, int val, int[] result, int idx, int smaller) {
    if (node == null) {
        result[idx] = smaller;
        return new AugNode(val);
    }
    if (val < node.val) {
        node.leftSize++;
        node.left = insert(node.left, val, result, idx, smaller);
    } else if (val > node.val) {
        node.right = insert(node.right, val, result, idx, 
                           smaller + node.leftSize + node.dupCount);
    } else {
        node.dupCount++;
        result[idx] = smaller + node.leftSize;
    }
    return node;
}
```

### Note
In practice, merge sort approach is more reliable (no skew risk):
- Time: O(n log n) guaranteed
- BST approach: O(n log n) average, O(n^2) worst case without balancing

### Complexity
- BST: O(n log n) average, O(n^2) worst
- Merge sort / BIT: O(n log n) guaranteed

---

## Pattern 15: AVL / Red-Black Tree Concepts

### When to Mention in Design Interviews
- "How would you implement an ordered map?" → Red-Black Tree (Java TreeMap)
- "What if insertions are sorted?" → Plain BST degenerates to O(n); need balancing
- "Trade-offs of different balanced BSTs?"

### Quick Reference

| Property | AVL | Red-Black |
|----------|-----|-----------|
| Balance guarantee | Height diff <= 1 | Black-height balanced |
| Search | Faster (stricter balance) | Slightly slower |
| Insert/Delete | More rotations | Fewer rotations |
| Use case | Read-heavy | Write-heavy |
| Real-world | Databases | Language std libs (TreeMap, std::map) |

### AVL Rotation Concept
```
Right Rotation (LL case):     Left Rotation (RR case):
      z                y            z              y
     / \             /   \         / \           /   \
    y   T4   →      x     z      T1   y   →    z     x
   / \             / \   / \         / \       / \   / \
  x   T3          T1 T2 T3 T4      T2  x     T1 T2 T3 T4
 / \                                   / \
T1  T2                                T3  T4
```

### What to Say in Interviews
> "In practice I'd use TreeMap/TreeSet which is backed by a Red-Black tree giving O(log n) guarantees. For this problem, I'll implement a plain BST since the focus is on the algorithm, but I'm aware that without balancing, worst case is O(n) for skewed input."

---

## Augmented BST Concept

Store additional information at each node to answer queries in O(h):

```java
class AugmentedNode {
    int val;
    int size;       // subtree size → rank queries, kth element
    int sum;        // subtree sum → range sum queries
    int height;     // for AVL balancing
    AugmentedNode left, right;
}

// Update on insert/delete:
void updateSize(AugmentedNode node) {
    node.size = 1 + size(node.left) + size(node.right);
}
```

### Common Augmentations

| Field | Enables |
|-------|---------|
| size | Kth element, rank, count in range |
| sum | Range sum queries |
| height | AVL balancing |
| min/max | Range min/max without full traversal |

---

## When Inorder Traversal Is the Key Insight

These problems all reduce to "inorder = sorted sequence":

| Problem | Inorder Insight |
|---------|----------------|
| Validate BST | Inorder must be strictly increasing |
| Recover BST | Find violations in inorder sequence |
| Kth smallest | Kth element in inorder |
| BST to Greater Tree | Reverse inorder accumulation |
| Two Sum in BST | Two pointers on inorder (or two iterators) |
| BST Iterator | Controlled/paused inorder |
| Merge Two BSTs | Merge two inorder sequences |

---

## Master Decision Table

| Problem Pattern | Technique | Time |
|----------------|-----------|------|
| Search/Insert/Delete | Standard BST ops | O(h) |
| Validate | Min/max bounds recursion | O(n) |
| Kth smallest | Inorder + counter | O(h+k) |
| LCA | BST property split | O(h) |
| Sorted → BST | Mid-as-root recursion | O(n) |
| Iterator | Stack-based controlled inorder | O(1) amortized |
| Two swapped | Track inorder violations | O(n) |
| Trim range | Recursive prune | O(n) |
| Greater tree | Reverse inorder + running sum | O(n) |
| Closest value | Binary search walk | O(h) |
| Closest K | Two stacks (pred/succ) | O(h+k) |
| Count smaller | Augmented BST or merge sort | O(n log n) |
| Frequent rank queries | Augmented BST with size | O(h) per query |

---

## Common Mistakes

1. **Validate BST**: Only checking immediate children, not entire subtree bounds
2. **Delete**: Forgetting to handle the "two children" case properly
3. **Assuming balanced**: Plain BST is O(n) worst case — state this in interviews
4. **Integer overflow in bounds**: Use `Long.MIN_VALUE/MAX_VALUE` for validation bounds
5. **Inorder with global state**: Reset class-level variables between test cases
