# Binary Tree Patterns

## Decision Flowchart

```
Given a binary tree problem, ask:
                                    
1. Do I need level-by-level info?  ──YES──> BFS (Queue)
   │NO
2. Do I need to track a global optimum    
   while returning local info?     ──YES──> Bottom-Up DFS + global variable
   │NO                                      (diameter, max path sum, cameras)
3. Do I need to pass info downward?──YES──> Top-Down DFS (pass params down)
   │NO                                      (path sum, depth, boundaries)
4. Do I need to construct/reconstruct?──YES─> Divide & Conquer (build subtrees)
   │NO
5. Do I need O(1) space traversal? ──YES──> Morris Traversal
   │NO
6. Default ────────────────────────────────> Recursive DFS (pick traversal order)
```

## Top-Down vs Bottom-Up Paradigm

| Aspect | Top-Down | Bottom-Up |
|--------|----------|-----------|
| Direction | Root → Leaves | Leaves → Root |
| Info flow | Pass parameters down | Return values up |
| When to use | Need ancestor info at each node | Need subtree info to compute answer |
| Examples | Path sum, max depth (simple), validate BST | Diameter, balanced check, LCA |
| Pattern | `void dfs(node, accumulated_state)` | `int dfs(node)` returns subtree info |
| Global var? | Sometimes (track best) | Often (track optimum across all subtrees) |

**Key Insight: "What to return vs what to track globally"**

Many tree problems require computing something that spans a subtree (e.g., diameter = longest path through some node). The trick:
- **Return**: what the parent needs (e.g., height of subtree)
- **Track globally**: the actual answer (e.g., max diameter seen so far)

These are DIFFERENT things. The return value serves the recursion; the global tracks the answer.

```java
// Pattern: return one thing, track another
int globalAnswer = 0;

int dfs(TreeNode node) {
    if (node == null) return baseCase;
    int left = dfs(node.left);
    int right = dfs(node.right);
    
    // UPDATE global with what THIS node contributes
    globalAnswer = Math.max(globalAnswer, f(left, right, node));
    
    // RETURN what parent needs
    return g(left, right, node);
}
```

## Tree Visualization Conventions

```
       1          Depth 0
      / \
     2   3        Depth 1
    / \   \
   4   5   6      Depth 2

Node representation: TreeNode { int val; TreeNode left, right; }
null children drawn as X or omitted
Path: sequence of nodes from ancestor to descendant
Diameter: longest path between ANY two nodes (may not pass through root)
```

---

## 1. Tree Traversals

### Signal
- "Visit all nodes in specific order"
- Need to process tree systematically
- Foundation for nearly all tree algorithms

### Template (Recursive)

```java
// Inorder: Left → Root → Right (gives sorted order for BST)
void inorder(TreeNode root) {
    if (root == null) return;
    inorder(root.left);
    process(root);        // ← position determines traversal type
    inorder(root.right);
}

// Preorder: Root → Left → Right (copy/serialize tree structure)
void preorder(TreeNode root) {
    if (root == null) return;
    process(root);
    preorder(root.left);
    preorder(root.right);
}

// Postorder: Left → Right → Root (delete tree, compute heights)
void postorder(TreeNode root) {
    if (root == null) return;
    postorder(root.left);
    postorder(root.right);
    process(root);
}
```

### Template (Iterative with Explicit Stack)

```java
// Iterative Inorder
List<Integer> inorderIterative(TreeNode root) {
    List<Integer> result = new ArrayList<>();
    Deque<TreeNode> stack = new ArrayDeque<>();
    TreeNode curr = root;
    
    while (curr != null || !stack.isEmpty()) {
        // Go all the way left
        while (curr != null) {
            stack.push(curr);
            curr = curr.left;
        }
        curr = stack.pop();
        result.add(curr.val);   // process
        curr = curr.right;       // move to right subtree
    }
    return result;
}

// Iterative Preorder
List<Integer> preorderIterative(TreeNode root) {
    List<Integer> result = new ArrayList<>();
    if (root == null) return result;
    Deque<TreeNode> stack = new ArrayDeque<>();
    stack.push(root);
    
    while (!stack.isEmpty()) {
        TreeNode node = stack.pop();
        result.add(node.val);           // process immediately
        if (node.right != null) stack.push(node.right); // right first (LIFO)
        if (node.left != null) stack.push(node.left);
    }
    return result;
}

// Iterative Postorder (two-stack or reverse trick)
List<Integer> postorderIterative(TreeNode root) {
    LinkedList<Integer> result = new LinkedList<>();
    if (root == null) return result;
    Deque<TreeNode> stack = new ArrayDeque<>();
    stack.push(root);
    
    while (!stack.isEmpty()) {
        TreeNode node = stack.pop();
        result.addFirst(node.val);      // add to FRONT (reverse of pre-order)
        if (node.left != null) stack.push(node.left);   // left first
        if (node.right != null) stack.push(node.right);
    }
    return result;
}
```

### Visualization

```
Tree:      1
          / \
         2   3
        / \
       4   5

Inorder:   4, 2, 5, 1, 3    (Left-Root-Right)
Preorder:  1, 2, 4, 5, 3    (Root-Left-Right)  
Postorder: 4, 5, 2, 3, 1    (Left-Right-Root)

Iterative Inorder Stack Trace:
  push 1, push 2, push 4
  pop 4 → output 4, curr=null
  pop 2 → output 2, curr=5
  push 5
  pop 5 → output 5, curr=null
  pop 1 → output 1, curr=3
  push 3
  pop 3 → output 3, curr=null
```

### Complexity
- Time: O(n) for all traversals
- Space: O(h) for recursive/iterative stack, where h = height (O(log n) balanced, O(n) skewed)

---

## 2. Level-Order Traversal / BFS

### Signal
- "Level by level", "layer by layer", "zigzag"
- "Right side view", "left side view"
- "Average of levels", "largest value in each row"
- Need to know which level a node belongs to

### Template

```java
// Standard BFS with level separation
List<List<Integer>> levelOrder(TreeNode root) {
    List<List<Integer>> result = new ArrayList<>();
    if (root == null) return result;
    
    Queue<TreeNode> queue = new LinkedList<>();
    queue.offer(root);
    
    while (!queue.isEmpty()) {
        int levelSize = queue.size();  // KEY: snapshot current level size
        List<Integer> level = new ArrayList<>();
        
        for (int i = 0; i < levelSize; i++) {
            TreeNode node = queue.poll();
            level.add(node.val);
            if (node.left != null) queue.offer(node.left);
            if (node.right != null) queue.offer(node.right);
        }
        result.add(level);
    }
    return result;
}
```

### Variants

```java
// Zigzag Level Order (LC 103)
List<List<Integer>> zigzagLevelOrder(TreeNode root) {
    List<List<Integer>> result = new ArrayList<>();
    if (root == null) return result;
    Queue<TreeNode> queue = new LinkedList<>();
    queue.offer(root);
    boolean leftToRight = true;
    
    while (!queue.isEmpty()) {
        int size = queue.size();
        LinkedList<Integer> level = new LinkedList<>();
        for (int i = 0; i < size; i++) {
            TreeNode node = queue.poll();
            if (leftToRight) level.addLast(node.val);
            else level.addFirst(node.val);
            if (node.left != null) queue.offer(node.left);
            if (node.right != null) queue.offer(node.right);
        }
        result.add(level);
        leftToRight = !leftToRight;
    }
    return result;
}

// Right Side View (LC 199)
List<Integer> rightSideView(TreeNode root) {
    List<Integer> result = new ArrayList<>();
    if (root == null) return result;
    Queue<TreeNode> queue = new LinkedList<>();
    queue.offer(root);
    
    while (!queue.isEmpty()) {
        int size = queue.size();
        for (int i = 0; i < size; i++) {
            TreeNode node = queue.poll();
            if (i == size - 1) result.add(node.val); // last node in level
            if (node.left != null) queue.offer(node.left);
            if (node.right != null) queue.offer(node.right);
        }
    }
    return result;
}

// Level Averages (LC 637)
List<Double> averageOfLevels(TreeNode root) {
    List<Double> result = new ArrayList<>();
    Queue<TreeNode> queue = new LinkedList<>();
    queue.offer(root);
    
    while (!queue.isEmpty()) {
        int size = queue.size();
        double sum = 0;
        for (int i = 0; i < size; i++) {
            TreeNode node = queue.poll();
            sum += node.val;
            if (node.left != null) queue.offer(node.left);
            if (node.right != null) queue.offer(node.right);
        }
        result.add(sum / size);
    }
    return result;
}
```

### Complexity
- Time: O(n)
- Space: O(w) where w = max width of tree (up to n/2 at last level for complete tree)

---

## 3. Tree Height / Maximum Depth

### Signal
- "Maximum depth", "height of tree"
- Building block for many other problems

### Template

```java
// The classic one-liner (bottom-up)
int maxDepth(TreeNode root) {
    if (root == null) return 0;
    return 1 + Math.max(maxDepth(root.left), maxDepth(root.right));
}

// Top-down approach (passing depth as parameter)
int answer = 0;
void maxDepthTopDown(TreeNode root, int depth) {
    if (root == null) return;
    if (root.left == null && root.right == null) {
        answer = Math.max(answer, depth);
    }
    maxDepthTopDown(root.left, depth + 1);
    maxDepthTopDown(root.right, depth + 1);
}
```

### Visualization

```
       1          
      / \         maxDepth = 3
     2   3        
    /             
   4              height(1) = 1 + max(height(2), height(3))
                         = 1 + max(2, 1) = 3
```

### Complexity
- Time: O(n)
- Space: O(h) recursion stack

---

## 4. Balanced Binary Tree Check

### Signal
- "Is the tree height-balanced?" (every node's subtree heights differ by at most 1)
- LC 110

### Template (O(n) bottom-up)

```java
// Return height if balanced, -1 if not (avoids redundant computation)
public boolean isBalanced(TreeNode root) {
    return checkHeight(root) != -1;
}

private int checkHeight(TreeNode node) {
    if (node == null) return 0;
    
    int left = checkHeight(node.left);
    if (left == -1) return -1;          // early termination (prune)
    
    int right = checkHeight(node.right);
    if (right == -1) return -1;         // early termination
    
    if (Math.abs(left - right) > 1) return -1;  // unbalanced at this node
    
    return 1 + Math.max(left, right);   // return height normally
}
```

### Key Insight
- Naive approach: compute height at every node → O(n log n) or O(n²)
- Bottom-up: compute height AND check balance in single pass → O(n)
- Use sentinel value (-1) to propagate "unbalanced" status upward

### Complexity
- Time: O(n) - each node visited once
- Space: O(h) recursion stack

---

## 5. Diameter of Binary Tree

### Signal
- "Longest path between any two nodes"
- "Diameter" (number of edges on longest path)
- LC 543

### Template

```java
int diameter = 0;

public int diameterOfBinaryTree(TreeNode root) {
    height(root);
    return diameter;
}

private int height(TreeNode node) {
    if (node == null) return 0;
    
    int left = height(node.left);
    int right = height(node.right);
    
    // Update global: path through this node = left + right
    diameter = Math.max(diameter, left + right);
    
    // Return: height of subtree rooted here
    return 1 + Math.max(left, right);
}
```

### Visualization

```
       1
      / \
     2   3        Diameter = 3 (path: 4→2→1→3)
    /               but could be entirely in a subtree:
   4              
                       1
                      /
                     2       Diameter = 4 (path: 5→4→2→3→6)
                    / \      doesn't pass through root!
                   4   3
                  /     \
                 5       6
```

### Key Insight
- Diameter through node X = height(X.left) + height(X.right)
- Answer might NOT pass through root → need global max
- **Return height** (for parent), **track diameter** (for answer)

### Complexity
- Time: O(n)
- Space: O(h)

---

## 6. Lowest Common Ancestor (LCA)

### Signal
- "Lowest common ancestor of two nodes"
- "First shared ancestor"
- LC 236

### Template

```java
// Postorder: check left subtree, check right subtree, decide at current
TreeNode lowestCommonAncestor(TreeNode root, TreeNode p, TreeNode q) {
    if (root == null || root == p || root == q) return root;
    
    TreeNode left = lowestCommonAncestor(root.left, p, q);
    TreeNode right = lowestCommonAncestor(root.right, p, q);
    
    // Both found → current node is LCA
    if (left != null && right != null) return root;
    
    // One found → propagate it up
    return left != null ? left : right;
}
```

### Visualization

```
       3
      / \
     5   1        LCA(5, 1) = 3  (found in both subtrees)
    / \ / \       LCA(5, 4) = 5  (5 is ancestor of 4)
   6  2 0  8     LCA(6, 2) = 5  (both in left subtree of 5)
     / \
    7   4
```

### Key Insight
- If current node IS p or q, return it immediately (it could be ancestor of the other)
- If p and q are in different subtrees → current node is LCA
- If both in same subtree → LCA is deeper, propagated up from that subtree
- Assumes both p and q exist in tree

### Complexity
- Time: O(n)
- Space: O(h)

---

## 7. Path Sum Problems

### Signal
- "Path from root to leaf with target sum"
- "Find all such paths"
- "Path can start anywhere"

### Template

```java
// Path Sum I (LC 112): Does any root-to-leaf path = target?
boolean hasPathSum(TreeNode root, int targetSum) {
    if (root == null) return false;
    if (root.left == null && root.right == null) {
        return targetSum == root.val;  // leaf check
    }
    return hasPathSum(root.left, targetSum - root.val) ||
           hasPathSum(root.right, targetSum - root.val);
}

// Path Sum II (LC 113): Find ALL root-to-leaf paths = target
List<List<Integer>> pathSum(TreeNode root, int targetSum) {
    List<List<Integer>> result = new ArrayList<>();
    dfs(root, targetSum, new ArrayList<>(), result);
    return result;
}

void dfs(TreeNode node, int remain, List<Integer> path, List<List<Integer>> result) {
    if (node == null) return;
    path.add(node.val);
    
    if (node.left == null && node.right == null && remain == node.val) {
        result.add(new ArrayList<>(path));  // copy!
    } else {
        dfs(node.left, remain - node.val, path, result);
        dfs(node.right, remain - node.val, path, result);
    }
    
    path.remove(path.size() - 1);  // backtrack
}

// Path Sum III (LC 437): Path can start/end ANYWHERE (but goes downward)
// Key insight: prefix sum technique on tree paths
int pathSumIII(TreeNode root, int targetSum) {
    Map<Long, Integer> prefixMap = new HashMap<>();
    prefixMap.put(0L, 1);  // empty prefix
    return dfs(root, 0L, targetSum, prefixMap);
}

int dfs(TreeNode node, long currSum, int target, Map<Long, Integer> prefixMap) {
    if (node == null) return 0;
    
    currSum += node.val;
    // How many prefixes exist such that currSum - prefix = target?
    int count = prefixMap.getOrDefault(currSum - target, 0);
    
    prefixMap.merge(currSum, 1, Integer::sum);
    count += dfs(node.left, currSum, target, prefixMap);
    count += dfs(node.right, currSum, target, prefixMap);
    prefixMap.merge(currSum, -1, Integer::sum);  // backtrack
    
    return count;
}
```

### Key Insight for Path Sum III
- Same prefix sum trick as subarray sum on arrays
- "Remove" prefix when backtracking (tree has branching paths unlike array)
- currSum - target = prefix we need to have seen

### Complexity
- I: O(n) time, O(h) space
- II: O(n) time, O(h) space (excluding output)
- III: O(n) time, O(n) space (prefix map can hold up to n entries)

---

## 8. Binary Tree Maximum Path Sum

### Signal
- "Maximum path sum" where path = any sequence of connected nodes
- Path does NOT need to pass through root or go root-to-leaf
- LC 124

### Template

```java
int maxSum = Integer.MIN_VALUE;

public int maxPathSum(TreeNode root) {
    gainFromSubtree(root);
    return maxSum;
}

private int gainFromSubtree(TreeNode node) {
    if (node == null) return 0;
    
    // Max gain from left/right (ignore negative paths: clamp to 0)
    int leftGain = Math.max(0, gainFromSubtree(node.left));
    int rightGain = Math.max(0, gainFromSubtree(node.right));
    
    // Path through this node using BOTH children (potential answer)
    maxSum = Math.max(maxSum, node.val + leftGain + rightGain);
    
    // Return to parent: can only use ONE child (can't fork)
    return node.val + Math.max(leftGain, rightGain);
}
```

### Visualization

```
      -10
      /  \
     9    20       Max path: 15 → 20 → 7 = 42
         /  \      
        15   7     

At node 20: leftGain=15, rightGain=7
  Update global: -10... no, 20+15+7=42 ✓
  Return to parent: 20 + max(15,7) = 35

At node -10: leftGain=9, rightGain=35
  Update global: max(42, -10+9+35) = max(42, 34) = 42
  Return: -10 + max(9,35) = 25
```

### Key Insight
- **Can't go both left AND right when returning to parent** (path would fork)
- At each node, we have a choice: include in path going up, or this node is the "turn point"
- Global tracks paths that turn; return tracks straight paths going up
- Clamp negative gains to 0 (better to not take that branch at all)

### Complexity
- Time: O(n)
- Space: O(h)

---

## 9. Construct Tree from Traversals

### Signal
- "Construct binary tree from preorder and inorder"
- "Construct from postorder and inorder"
- LC 105, 106, 889

### Template

```java
// From Preorder + Inorder (LC 105)
Map<Integer, Integer> inorderIndex;
int preIdx = 0;

public TreeNode buildTree(int[] preorder, int[] inorder) {
    inorderIndex = new HashMap<>();
    for (int i = 0; i < inorder.length; i++) {
        inorderIndex.put(inorder[i], i);
    }
    return build(preorder, 0, inorder.length - 1);
}

private TreeNode build(int[] preorder, int inLeft, int inRight) {
    if (inLeft > inRight) return null;
    
    int rootVal = preorder[preIdx++];
    TreeNode root = new TreeNode(rootVal);
    
    int inMid = inorderIndex.get(rootVal);  // root's position in inorder
    
    root.left = build(preorder, inLeft, inMid - 1);   // left subtree
    root.right = build(preorder, inMid + 1, inRight); // right subtree
    
    return root;
}

// From Postorder + Inorder (LC 106)
// Same idea but traverse postorder from RIGHT, build right subtree FIRST
int postIdx;

public TreeNode buildTreePost(int[] inorder, int[] postorder) {
    inorderIndex = new HashMap<>();
    for (int i = 0; i < inorder.length; i++) {
        inorderIndex.put(inorder[i], i);
    }
    postIdx = postorder.length - 1;
    return buildPost(postorder, 0, inorder.length - 1);
}

private TreeNode buildPost(int[] postorder, int inLeft, int inRight) {
    if (inLeft > inRight) return null;
    
    int rootVal = postorder[postIdx--];
    TreeNode root = new TreeNode(rootVal);
    int inMid = inorderIndex.get(rootVal);
    
    root.right = buildPost(postorder, inMid + 1, inRight); // RIGHT first!
    root.left = buildPost(postorder, inLeft, inMid - 1);
    
    return root;
}
```

### Visualization

```
Preorder: [3, 9, 20, 15, 7]    Root is always first in preorder
Inorder:  [9, 3, 15, 20, 7]    Split by root → left subtree | right subtree

Step 1: root = 3 (preorder[0])
        inorder: [9] | 3 | [15, 20, 7]
                 left      right

Step 2: left subtree root = 9 (preorder[1])
        right subtree root = 20 (preorder[2])

Result:    3
          / \
         9  20
           /  \
          15   7
```

### Key Insight
- Preorder: first element is root; Postorder: last element is root
- Inorder: root splits array into left subtree elements | right subtree elements
- HashMap for O(1) index lookup in inorder (avoids O(n) search each time)
- For postorder: process from end, build right subtree before left

### Complexity
- Time: O(n)
- Space: O(n) for HashMap + O(h) recursion

---

## 10. Serialize / Deserialize Binary Tree

### Signal
- "Convert tree to string and back"
- "Design encode/decode"
- LC 297

### Template (BFS Level-Order)

```java
// Serialize: BFS with "null" markers
public String serialize(TreeNode root) {
    if (root == null) return "";
    StringBuilder sb = new StringBuilder();
    Queue<TreeNode> queue = new LinkedList<>();
    queue.offer(root);
    
    while (!queue.isEmpty()) {
        TreeNode node = queue.poll();
        if (node == null) {
            sb.append("null,");
        } else {
            sb.append(node.val).append(",");
            queue.offer(node.left);
            queue.offer(node.right);
        }
    }
    return sb.toString();
}

// Deserialize: BFS reconstruction
public TreeNode deserialize(String data) {
    if (data.isEmpty()) return null;
    String[] vals = data.split(",");
    TreeNode root = new TreeNode(Integer.parseInt(vals[0]));
    Queue<TreeNode> queue = new LinkedList<>();
    queue.offer(root);
    int i = 1;
    
    while (!queue.isEmpty()) {
        TreeNode node = queue.poll();
        if (!vals[i].equals("null")) {
            node.left = new TreeNode(Integer.parseInt(vals[i]));
            queue.offer(node.left);
        }
        i++;
        if (!vals[i].equals("null")) {
            node.right = new TreeNode(Integer.parseInt(vals[i]));
            queue.offer(node.right);
        }
        i++;
    }
    return root;
}
```

### Template (DFS Preorder)

```java
// Serialize: preorder DFS
public String serialize(TreeNode root) {
    StringBuilder sb = new StringBuilder();
    serializeDFS(root, sb);
    return sb.toString();
}

void serializeDFS(TreeNode node, StringBuilder sb) {
    if (node == null) { sb.append("null,"); return; }
    sb.append(node.val).append(",");
    serializeDFS(node.left, sb);
    serializeDFS(node.right, sb);
}

// Deserialize: preorder reconstruction
public TreeNode deserialize(String data) {
    Queue<String> tokens = new LinkedList<>(Arrays.asList(data.split(",")));
    return deserializeDFS(tokens);
}

TreeNode deserializeDFS(Queue<String> tokens) {
    String val = tokens.poll();
    if (val.equals("null")) return null;
    TreeNode node = new TreeNode(Integer.parseInt(val));
    node.left = deserializeDFS(tokens);
    node.right = deserializeDFS(tokens);
    return node;
}
```

### Complexity
- Time: O(n) for both serialize and deserialize
- Space: O(n)

---

## 11. Flatten Binary Tree to Linked List

### Signal
- "Flatten to linked list in-place" (preorder, using right pointers)
- LC 114

### Template

```java
// Approach 1: Reverse postorder (right → left → root)
TreeNode prev = null;

public void flatten(TreeNode root) {
    if (root == null) return;
    flatten(root.right);
    flatten(root.left);
    root.right = prev;
    root.left = null;
    prev = root;
}

// Approach 2: Iterative Morris-like (O(1) space, no recursion)
public void flattenIterative(TreeNode root) {
    TreeNode curr = root;
    while (curr != null) {
        if (curr.left != null) {
            // Find rightmost node of left subtree
            TreeNode rightmost = curr.left;
            while (rightmost.right != null) {
                rightmost = rightmost.right;
            }
            // Connect right subtree after left's rightmost
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
     1              1
    / \              \
   2   5     →       2
  / \   \             \
 3   4   6             3
                        \
                         4
                          \
                           5
                            \
                             6

Morris-like at node 1:
  left subtree's rightmost = 4
  4.right = 5 (connect right subtree)
  1.right = 2 (move left to right)
  1.left = null
```

### Complexity
- Approach 1: O(n) time, O(h) space (recursion)
- Approach 2: O(n) time, O(1) space

---

## 12. Symmetric Tree / Same Tree / Subtree Check

### Signal
- "Is tree symmetric?" (mirror of itself)
- "Are two trees identical?"
- "Is t a subtree of s?"

### Template

```java
// Symmetric Tree (LC 101)
public boolean isSymmetric(TreeNode root) {
    return isMirror(root.left, root.right);
}

boolean isMirror(TreeNode t1, TreeNode t2) {
    if (t1 == null && t2 == null) return true;
    if (t1 == null || t2 == null) return false;
    return t1.val == t2.val 
        && isMirror(t1.left, t2.right)   // outer pair
        && isMirror(t1.right, t2.left);  // inner pair
}

// Same Tree (LC 100)
boolean isSameTree(TreeNode p, TreeNode q) {
    if (p == null && q == null) return true;
    if (p == null || q == null) return false;
    return p.val == q.val 
        && isSameTree(p.left, q.left) 
        && isSameTree(p.right, q.right);
}

// Subtree of Another Tree (LC 572)
boolean isSubtree(TreeNode root, TreeNode subRoot) {
    if (root == null) return false;
    if (isSameTree(root, subRoot)) return true;
    return isSubtree(root.left, subRoot) || isSubtree(root.right, subRoot);
}
```

### Key Insight
- Symmetric = left subtree is mirror of right subtree
- Mirror: compare outer children (L.left vs R.right) and inner (L.right vs R.left)
- Subtree: try matching at every node → O(m*n) worst case
  - Can optimize to O(m+n) using tree hashing or serialization

### Complexity
- Symmetric/Same: O(n) time, O(h) space
- Subtree: O(m*n) time worst case, O(h) space

---

## 13. Vertical Order Traversal

### Signal
- "Vertical order", "columns of a tree"
- LC 314, LC 987

### Template

```java
// BFS approach with column tracking
public List<List<Integer>> verticalOrder(TreeNode root) {
    List<List<Integer>> result = new ArrayList<>();
    if (root == null) return result;
    
    TreeMap<Integer, List<Integer>> columnMap = new TreeMap<>();
    Queue<int[]> queue = new LinkedList<>(); // Not ideal; use pair class
    Queue<TreeNode> nodeQueue = new LinkedList<>();
    
    nodeQueue.offer(root);
    queue.offer(new int[]{0}); // column
    
    while (!nodeQueue.isEmpty()) {
        TreeNode node = nodeQueue.poll();
        int col = queue.poll()[0];
        
        columnMap.computeIfAbsent(col, k -> new ArrayList<>()).add(node.val);
        
        if (node.left != null) {
            nodeQueue.offer(node.left);
            queue.offer(new int[]{col - 1});
        }
        if (node.right != null) {
            nodeQueue.offer(node.right);
            queue.offer(new int[]{col + 1});
        }
    }
    
    result.addAll(columnMap.values());
    return result;
}

// LC 987: Vertical Order with row-level sorting
// Uses TreeMap<col, TreeMap<row, PriorityQueue<Integer>>>
public List<List<Integer>> verticalTraversal(TreeNode root) {
    TreeMap<Integer, TreeMap<Integer, PriorityQueue<Integer>>> map = new TreeMap<>();
    dfs(root, 0, 0, map);
    
    List<List<Integer>> result = new ArrayList<>();
    for (var colMap : map.values()) {
        List<Integer> col = new ArrayList<>();
        for (var pq : colMap.values()) {
            while (!pq.isEmpty()) col.add(pq.poll());
        }
        result.add(col);
    }
    return result;
}

void dfs(TreeNode node, int row, int col, 
         TreeMap<Integer, TreeMap<Integer, PriorityQueue<Integer>>> map) {
    if (node == null) return;
    map.computeIfAbsent(col, k -> new TreeMap<>())
       .computeIfAbsent(row, k -> new PriorityQueue<>())
       .offer(node.val);
    dfs(node.left, row + 1, col - 1, map);
    dfs(node.right, row + 1, col + 1, map);
}
```

### Visualization

```
       1 (col=0)
      / \
     2   3          col: -1  0  1
    / \   \              2   1  3
   4   5   6             4   5  6
                              ↑ 5 is col=0 (left of right child)

Columns: {-1:[2,4], 0:[1,5], 1:[3,6]}
```

### Complexity
- Time: O(n log n) due to TreeMap
- Space: O(n)

---

## 14. Count Complete Tree Nodes

### Signal
- "Count nodes in COMPLETE binary tree"
- Must be better than O(n)
- LC 222

### Template

```java
public int countNodes(TreeNode root) {
    if (root == null) return 0;
    
    int leftHeight = getLeftHeight(root);
    int rightHeight = getRightHeight(root);
    
    if (leftHeight == rightHeight) {
        // Perfect tree: 2^h - 1 nodes
        return (1 << leftHeight) - 1;
    }
    
    // Not perfect: recurse (one subtree will be perfect)
    return 1 + countNodes(root.left) + countNodes(root.right);
}

int getLeftHeight(TreeNode node) {
    int h = 0;
    while (node != null) { h++; node = node.left; }
    return h;
}

int getRightHeight(TreeNode node) {
    int h = 0;
    while (node != null) { h++; node = node.right; }
    return h;
}
```

### Key Insight
- Complete tree: all levels full except possibly last (filled left to right)
- If leftHeight == rightHeight → perfect binary tree → formula: 2^h - 1
- Otherwise recurse: at each level, ONE subtree must be perfect (short-circuit)
- At most O(log n) levels, each doing O(log n) height check → O(log²n)

### Complexity
- Time: O(log²n)
- Space: O(log n) recursion

---

## 15. Binary Tree Cameras

### Signal
- "Minimum cameras to monitor all nodes"
- Greedy on tree with state machine
- LC 968

### Template

```java
// States: 0 = needs coverage, 1 = has camera, 2 = covered (no camera)
int cameras = 0;

public int minCameraCover(TreeNode root) {
    if (dfs(root) == 0) cameras++; // root needs coverage
    return cameras;
}

// Postorder greedy: place cameras as high as possible (cover parent from child)
private int dfs(TreeNode node) {
    if (node == null) return 2; // null nodes are "covered" (don't need monitoring)
    
    int left = dfs(node.left);
    int right = dfs(node.right);
    
    // If any child needs coverage → must place camera HERE
    if (left == 0 || right == 0) {
        cameras++;
        return 1; // has camera
    }
    
    // If any child has camera → this node is covered
    if (left == 1 || right == 1) {
        return 2; // covered
    }
    
    // Both children are covered but no camera adjacent → needs coverage from parent
    return 0; // needs coverage
}
```

### Visualization

```
       0 ← needs camera (root check)    Final: add camera at root
      / \
     2   2   ← covered by children's cameras
    / \   \
   1   1   1  ← cameras placed here
  / \
 0   0  ← leaves need coverage → parent gets camera

Greedy insight: never put camera on leaf (wasteful). 
Put on leaf's parent → covers leaf, parent, and grandparent.
```

### Key Insight
- Postorder (bottom-up): decide based on children's states
- Greedy: delay camera placement as long as possible (push up)
- Leaves should NOT have cameras (cover only 1 direction); their parents should
- 3 states create clean state machine

### Complexity
- Time: O(n)
- Space: O(h)

---

## 16. Morris Traversal

### Signal
- "O(1) space tree traversal" (no stack, no recursion)
- Threading: temporarily modify tree structure

### Template

```java
// Morris Inorder Traversal - O(1) space, O(n) time
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
            TreeNode predecessor = curr.left;
            while (predecessor.right != null && predecessor.right != curr) {
                predecessor = predecessor.right;
            }
            
            if (predecessor.right == null) {
                // Create thread: predecessor → current
                predecessor.right = curr;
                curr = curr.left;
            } else {
                // Thread exists (second visit): remove thread, visit, go right
                predecessor.right = null;
                result.add(curr.val);
                curr = curr.right;
            }
        }
    }
    return result;
}

// Morris Preorder: same structure, but visit on FIRST encounter
List<Integer> morrisPreorder(TreeNode root) {
    List<Integer> result = new ArrayList<>();
    TreeNode curr = root;
    
    while (curr != null) {
        if (curr.left == null) {
            result.add(curr.val);
            curr = curr.right;
        } else {
            TreeNode predecessor = curr.left;
            while (predecessor.right != null && predecessor.right != curr) {
                predecessor = predecessor.right;
            }
            
            if (predecessor.right == null) {
                result.add(curr.val);   // visit HERE (before going left)
                predecessor.right = curr;
                curr = curr.left;
            } else {
                predecessor.right = null;
                curr = curr.right;
            }
        }
    }
    return result;
}
```

### Visualization

```
     1                Thread creation:
    / \               4's right → 1 (predecessor of 1)
   2   3              5's right → 1... no, 5's right → 2? Let's trace:
  / \
 4   5              curr=1: predecessor of 1 in left subtree = 5 (rightmost of left)
                      5.right = null → create thread: 5.right = 1, go left
                    curr=2: predecessor = 4 (rightmost of 2's left = 4)
                      4.right = null → create thread: 4.right = 2, go left
                    curr=4: left is null → visit 4, go right (thread → 2)
                    curr=2: predecessor = 4, 4.right == curr → remove thread
                      visit 2, go right → 5
                    curr=5: left is null → visit 5, go right (thread → 1)
                    curr=1: predecessor = 5, 5.right == curr → remove thread
                      visit 1, go right → 3
                    curr=3: left is null → visit 3, go right → null. Done.
                    
                    Output: 4, 2, 5, 1, 3 ✓ (inorder)
```

### Key Insight
- "Thread" = temporary right pointer from predecessor back to current node
- Each node is visited exactly twice (thread creation + thread removal)
- Tree structure is restored after traversal (threads removed)
- Use when O(1) space is critical and tree modification is allowed temporarily

### Complexity
- Time: O(n) - each edge traversed at most 3 times
- Space: O(1) - no stack or recursion

---

## Quick Reference: Problem → Pattern Mapping

| Problem | Pattern | Return | Track Globally |
|---------|---------|--------|----------------|
| Max Depth | Bottom-up | height | - |
| Balanced | Bottom-up | height or -1 | - |
| Diameter | Bottom-up | height | max diameter |
| Max Path Sum | Bottom-up | max single-branch gain | max path sum |
| Cameras | Bottom-up (greedy) | state {0,1,2} | camera count |
| LCA | Bottom-up | found node or null | - |
| Path Sum I | Top-down | boolean | - |
| Path Sum III | Top-down | count | - (uses prefix map) |
| Level Order | BFS | - | level lists |
| Vertical Order | BFS/DFS | - | column map |
| Serialize | BFS or Preorder DFS | string | - |
| Construct | Divide & Conquer | TreeNode | - |
| Flatten | Reverse postorder | - | prev pointer |
| Symmetric | Two-pointer recursion | boolean | - |
| Count Complete | Height comparison | count | - |
| Morris | Iterative threading | traversal order | - |

---

## Common Mistakes

1. **Forgetting null checks**: Always handle `root == null` first
2. **Confusing height vs depth**: Height = bottom-up (leaves=0 or 1), Depth = top-down (root=0)
3. **Path Sum leaf check**: Must verify BOTH children are null for leaf
4. **Max Path Sum negative clamp**: `Math.max(0, childGain)` - don't take negative paths
5. **LCA assumes existence**: Standard solution assumes both nodes exist in tree
6. **Diameter counts edges vs nodes**: Clarify if answer = edges or nodes-1
7. **Construct tree index management**: Preorder uses global index; don't pass/return it wrong
8. **Morris modifies tree**: Must restore if tree shouldn't be modified permanently
9. **Iterative postorder**: The "reverse pre-order trick" gives correct values but processes in different order - don't use when you need actual postorder processing side effects
