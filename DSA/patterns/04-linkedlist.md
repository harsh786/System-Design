# 04 - Linked List Patterns

## Decision Flowchart

```
Linked List Problem
│
├─ Cycle / Loop related?
│   └─ Floyd's Fast/Slow Pointer (#1)
│
├─ Need middle or kth element?
│   ├─ Middle → Fast/Slow (#1)
│   └─ Nth from end → Two-Pointer Gap (#5)
│
├─ Reverse all or part?
│   ├─ Full reverse → Iterative Reverse (#2)
│   ├─ Reverse sublist → Reverse Between (#2)
│   └─ Reverse k-groups → Reverse K-Group (#2)
│
├─ Merge / Sort?
│   ├─ Two sorted lists → Two-Pointer Merge (#3)
│   └─ K sorted lists → Heap or Divide & Conquer (#3)
│
├─ Head might change?
│   └─ Dummy Head Technique (#4)
│
├─ Two lists intersect?
│   └─ Two-Pointer Switch (#6)
│
├─ Reorder / Interleave?
│   └─ Find Middle + Reverse + Merge (#7)
│
├─ Deep copy with random pointers?
│   └─ HashMap or Interleave (#8)
│
└─ Arithmetic on lists?
    └─ Digit-by-Digit with Carry (#9)
```

---

## Common Node Definition

```java
public class ListNode {
    int val;
    ListNode next;
    ListNode(int val) { this.val = val; }
    ListNode(int val, ListNode next) { this.val = val; this.next = next; }
}
```

---

## Pattern 1: Fast/Slow Pointer (Floyd's Algorithm)

### Signal
- "Detect cycle", "find cycle start", "find middle node"
- Any problem requiring O(1) space traversal at different speeds

### 1A: Cycle Detection

#### Mathematical Proof

```
Let:
  L = distance from head to cycle start
  C = cycle length
  K = distance from cycle start to meeting point

When slow enters cycle, fast is already K steps into cycle (where K = L mod C).
Fast is (C - K) steps behind slow.
Each step, fast gains 1 on slow → they meet after (C - K) steps.

At meeting point:
  slow traveled: L + (C - K)
  fast traveled: 2(L + C - K)   [fast moves 2x]
  fast also traveled: L + nC + (C - K)  for some n >= 1

  ∴ 2(L + C - K) = L + nC + C - K
    L = (n-1)C + K

This means: distance from head to cycle start = 
             distance from meeting point to cycle start (modulo C)
```

#### Template

```java
public boolean hasCycle(ListNode head) {
    ListNode slow = head, fast = head;
    while (fast != null && fast.next != null) {
        slow = slow.next;
        fast = fast.next.next;
        if (slow == fast) return true;
    }
    return false;
}
```

### 1B: Find Cycle Start

```java
public ListNode detectCycleStart(ListNode head) {
    ListNode slow = head, fast = head;
    while (fast != null && fast.next != null) {
        slow = slow.next;
        fast = fast.next.next;
        if (slow == fast) {
            // Phase 2: move one pointer to head, advance both by 1
            ListNode p = head;
            while (p != slow) {
                p = p.next;
                slow = slow.next;
            }
            return p; // cycle start
        }
    }
    return null;
}
```

#### Visualization

```
Phase 1 - Finding meeting point:
  head ──→ ● ──→ ● ──→ [C] ──→ ● ──→ ● ──→ ●
                          ↑                    │
                          └────────────────────┘
                               ↑
                          Meeting point M

Phase 2 - Finding cycle start:
  p starts at head, slow stays at M
  Both advance 1 step → meet at cycle start [C]
```

### 1C: Find Middle

```java
public ListNode findMiddle(ListNode head) {
    ListNode slow = head, fast = head;
    while (fast != null && fast.next != null) {
        slow = slow.next;
        fast = fast.next.next;
    }
    return slow; // for odd: exact middle, for even: second middle
}

// For first middle in even-length list:
public ListNode findFirstMiddle(ListNode head) {
    ListNode slow = head, fast = head;
    while (fast.next != null && fast.next.next != null) {
        slow = slow.next;
        fast = fast.next.next;
    }
    return slow;
}
```

### Variants
- Find cycle length (after detection, count steps in cycle)
- Happy Number (treat digit-square sequence as linked list)
- Find duplicate number in [1..n] array (indices as pointers)

### Complexity
| Operation | Time | Space |
|-----------|------|-------|
| Cycle detection | O(n) | O(1) |
| Find start | O(n) | O(1) |
| Find middle | O(n) | O(1) |

---

## Pattern 2: Reverse Linked List

### Signal
- "Reverse entire list", "reverse portion", "reverse in groups"
- Any problem where reversing pointer direction is needed

### 2A: Full Iterative Reverse

```java
public ListNode reverseList(ListNode head) {
    ListNode prev = null, curr = head;
    while (curr != null) {
        ListNode next = curr.next;  // save
        curr.next = prev;           // reverse
        prev = curr;                // advance prev
        curr = next;                // advance curr
    }
    return prev;
}
```

#### Visualization

```
Step 0: null ← [prev]   1 → 2 → 3 → null
                        [curr]
Step 1: null ← 1   2 → 3 → null
              [prev] [curr]
Step 2: null ← 1 ← 2   3 → null
                   [prev] [curr]
Step 3: null ← 1 ← 2 ← 3
                        [prev]  curr=null → DONE
```

### 2B: Reverse Between (positions left to right)

```java
// LC 92: Reverse Linked List II
public ListNode reverseBetween(ListNode head, int left, int right) {
    ListNode dummy = new ListNode(0, head);
    ListNode prev = dummy;
    
    // 1. Reach node before left
    for (int i = 1; i < left; i++) {
        prev = prev.next;
    }
    
    // 2. Reverse from left to right
    ListNode curr = prev.next;
    for (int i = 0; i < right - left; i++) {
        ListNode next = curr.next;
        curr.next = next.next;
        next.next = prev.next;
        prev.next = next;
    }
    
    return dummy.next;
}
```

#### Visualization

```
Reverse between positions 2 and 4:
dummy → 1 → [2 → 3 → 4] → 5
        prev  curr

Iteration 1: pull 3 in front of 2
dummy → 1 → 3 → 2 → 4 → 5
        prev      curr

Iteration 2: pull 4 in front of 3
dummy → 1 → 4 → 3 → 2 → 5
        prev           curr
```

### 2C: Reverse K-Group

```java
// LC 25: Reverse Nodes in k-Group
public ListNode reverseKGroup(ListNode head, int k) {
    ListNode dummy = new ListNode(0, head);
    ListNode groupPrev = dummy;
    
    while (true) {
        // Check if k nodes remain
        ListNode kth = getKth(groupPrev, k);
        if (kth == null) break;
        
        ListNode groupNext = kth.next;
        
        // Reverse the group
        ListNode prev = groupNext, curr = groupPrev.next;
        while (curr != groupNext) {
            ListNode next = curr.next;
            curr.next = prev;
            prev = curr;
            curr = next;
        }
        
        // Connect with previous part
        ListNode tmp = groupPrev.next;  // will be tail after reverse
        groupPrev.next = kth;           // kth is now head of reversed group
        groupPrev = tmp;                // move to end of reversed group
    }
    
    return dummy.next;
}

private ListNode getKth(ListNode node, int k) {
    while (node != null && k > 0) {
        node = node.next;
        k--;
    }
    return node;
}
```

#### Visualization

```
k=3:  dummy → [1 → 2 → 3] → [4 → 5 → 6] → 7 → 8
              groupPrev=dummy, kth=3, groupNext=4

After reverse group 1:
       dummy → [3 → 2 → 1] → [4 → 5 → 6] → 7 → 8
                          groupPrev=1

After reverse group 2:
       dummy → [3 → 2 → 1] → [6 → 5 → 4] → 7 → 8
                                         groupPrev=4
Remaining < k → stop
```

### Variants
- Reverse alternating k-groups
- Reverse in pairs (k=2 special case)
- Palindrome check (reverse second half, compare)

### Complexity
| Operation | Time | Space |
|-----------|------|-------|
| Full reverse | O(n) | O(1) |
| Reverse between | O(n) | O(1) |
| Reverse k-group | O(n) | O(1) |

---

## Pattern 3: Merge Sorted Lists

### Signal
- "Merge two/k sorted lists", "sort linked list"

### 3A: Merge Two Sorted Lists

```java
public ListNode mergeTwoLists(ListNode l1, ListNode l2) {
    ListNode dummy = new ListNode(0);
    ListNode curr = dummy;
    
    while (l1 != null && l2 != null) {
        if (l1.val <= l2.val) {
            curr.next = l1;
            l1 = l1.next;
        } else {
            curr.next = l2;
            l2 = l2.next;
        }
        curr = curr.next;
    }
    curr.next = (l1 != null) ? l1 : l2;
    return dummy.next;
}
```

### 3B: Merge K Sorted Lists — Min-Heap

```java
public ListNode mergeKLists(ListNode[] lists) {
    PriorityQueue<ListNode> pq = new PriorityQueue<>(
        (a, b) -> a.val - b.val
    );
    
    for (ListNode head : lists) {
        if (head != null) pq.offer(head);
    }
    
    ListNode dummy = new ListNode(0);
    ListNode curr = dummy;
    
    while (!pq.isEmpty()) {
        ListNode node = pq.poll();
        curr.next = node;
        curr = curr.next;
        if (node.next != null) pq.offer(node.next);
    }
    
    return dummy.next;
}
```

### 3C: Merge K Sorted Lists — Divide & Conquer

```java
public ListNode mergeKLists(ListNode[] lists) {
    if (lists == null || lists.length == 0) return null;
    return mergeRange(lists, 0, lists.length - 1);
}

private ListNode mergeRange(ListNode[] lists, int lo, int hi) {
    if (lo == hi) return lists[lo];
    int mid = lo + (hi - lo) / 2;
    ListNode left = mergeRange(lists, lo, mid);
    ListNode right = mergeRange(lists, mid + 1, hi);
    return mergeTwoLists(left, right);
}
```

#### Visualization

```
Heap approach:
  lists = [1→4→5, 1→3→4, 2→6]
  
  PQ: [1, 1, 2] → pop 1, push 4 → [1, 2, 4] → pop 1, push 3 → ...
  Result: 1→1→2→3→4→4→5→6

D&C approach:
  [L0, L1, L2, L3]  →  merge(L0,L1) and merge(L2,L3)  →  merge results
  Depth = log(k), each level processes all n nodes total
```

### Complexity
| Approach | Time | Space |
|----------|------|-------|
| Two lists | O(n + m) | O(1) |
| K lists — Heap | O(N log k) | O(k) |
| K lists — D&C | O(N log k) | O(log k) stack |

Where N = total nodes across all lists, k = number of lists.

---

## Pattern 4: Dummy Head Technique

### Signal
- Head of list might change (deletion of head, insertion before head)
- Simplifies edge cases for first node

### Template

```java
public ListNode removeElements(ListNode head, int val) {
    ListNode dummy = new ListNode(0, head);
    ListNode prev = dummy;
    ListNode curr = head;
    
    while (curr != null) {
        if (curr.val == val) {
            prev.next = curr.next;  // skip
        } else {
            prev = curr;
        }
        curr = curr.next;
    }
    
    return dummy.next;  // NOT head — head might have been removed
}
```

#### Visualization

```
Remove val=1 from: 1 → 1 → 2 → 3

dummy → 1 → 1 → 2 → 3
[prev] [curr]

curr.val == 1: prev.next = curr.next → dummy → 1 → 2 → 3
                                                [curr]
curr.val == 1: prev.next = curr.next → dummy → 2 → 3
                                                [curr]
curr.val != 1: prev = curr

Return dummy.next = 2 → 3 (original head was deleted!)
```

### When to Use
- Deleting nodes (head could be target)
- Merging lists (result head unknown)
- Partition list (two dummy heads for < and >= partitions)
- Any operation where first node isn't special

### Complexity
| Operation | Time | Space |
|-----------|------|-------|
| Any with dummy | Same as without | O(1) extra |

---

## Pattern 5: Nth Node from End

### Signal
- "Remove nth from end", "find nth from end"
- Any problem requiring position relative to tail

### Template

```java
public ListNode removeNthFromEnd(ListNode head, int n) {
    ListNode dummy = new ListNode(0, head);
    ListNode fast = dummy, slow = dummy;
    
    // Advance fast by n+1 steps (so slow stops BEFORE target)
    for (int i = 0; i <= n; i++) {
        fast = fast.next;
    }
    
    // Move both until fast hits null
    while (fast != null) {
        fast = fast.next;
        slow = slow.next;
    }
    
    // slow is now one before the target
    slow.next = slow.next.next;
    return dummy.next;
}
```

#### Visualization

```
Remove 2nd from end:  1 → 2 → 3 → 4 → 5

Step 1: Create gap of n+1 = 3
  dummy → 1 → 2 → 3 → 4 → 5 → null
  [slow]           [fast]

Step 2: Advance both until fast = null
  dummy → 1 → 2 → 3 → 4 → 5 → null
                   [slow]           [fast]

Step 3: slow.next = slow.next.next → skip node 4
  Result: 1 → 2 → 3 → 5
```

### Key Insight
Gap of (n+1) between fast and slow means when fast = null, slow is at the node **before** the target. This lets us delete in one pass.

### Variants
- Find (not delete) nth from end: gap of n, return slow
- Middle of list (same idea: fast moves 2x)

### Complexity
| Operation | Time | Space |
|-----------|------|-------|
| Nth from end | O(n) | O(1) |

---

## Pattern 6: Intersection Detection

### Signal
- "Find intersection point of two lists"
- Two lists potentially sharing a tail

### Mathematical Proof

```
List A: a1 → a2 → ... → c1 → c2 → ... → cn
List B: b1 → b2 → ... → b3 → c1 → c2 → ... → cn

Let:
  lenA = unique part of A + shared = a + c
  lenB = unique part of B + shared = b + c

Pointer pA traverses: A then B = a + c + b
Pointer pB traverses: B then A = b + c + a

a + c + b == b + c + a  ← ALWAYS EQUAL

Both pointers reach intersection node c1 at the same step.
If no intersection: both reach null simultaneously (a + c + b + c vs b + c + a + c 
but c=0, so a + b == b + a → both hit null).
```

### Template

```java
public ListNode getIntersectionNode(ListNode headA, ListNode headB) {
    ListNode pA = headA, pB = headB;
    
    while (pA != pB) {
        pA = (pA == null) ? headB : pA.next;
        pB = (pB == null) ? headA : pB.next;
    }
    
    return pA; // null if no intersection, intersection node otherwise
}
```

#### Visualization

```
A:      1 → 2 ↘
                 6 → 7 → null
B: 3 → 4 → 5 ↗

pA path: 1→2→6→7→null→3→4→5→6  (length a+c+b = 2+2+3 = 7 to reach 6)
pB path: 3→4→5→6→7→null→1→2→6  (length b+c+a = 3+2+2 = 7 to reach 6)
                                   ↑ meet here!
```

### Complexity
| Operation | Time | Space |
|-----------|------|-------|
| Find intersection | O(n + m) | O(1) |

---

## Pattern 7: Reorder / Interleave List

### Signal
- "Reorder list L0→Ln→L1→Ln-1→...", "zigzag merge"
- LC 143: Reorder List

### Template (3-Step Pattern)

```java
public void reorderList(ListNode head) {
    if (head == null || head.next == null) return;
    
    // Step 1: Find middle
    ListNode slow = head, fast = head;
    while (fast.next != null && fast.next.next != null) {
        slow = slow.next;
        fast = fast.next.next;
    }
    
    // Step 2: Reverse second half
    ListNode second = reverse(slow.next);
    slow.next = null; // cut
    
    // Step 3: Interleave merge
    ListNode first = head;
    while (second != null) {
        ListNode tmp1 = first.next;
        ListNode tmp2 = second.next;
        first.next = second;
        second.next = tmp1;
        first = tmp1;
        second = tmp2;
    }
}

private ListNode reverse(ListNode head) {
    ListNode prev = null, curr = head;
    while (curr != null) {
        ListNode next = curr.next;
        curr.next = prev;
        prev = curr;
        curr = next;
    }
    return prev;
}
```

#### Visualization

```
Input:  1 → 2 → 3 → 4 → 5

Step 1 - Find middle: slow=3
Step 2 - Reverse second half: 1→2→3  and  5→4
Step 3 - Interleave:
  first=1, second=5 → 1→5→2→...
  first=2, second=4 → 1→5→2→4→3

Output: 1 → 5 → 2 → 4 → 3
```

### Variants
- Odd-even linked list (group by index parity)
- Palindrome linked list (same 3 steps, then compare)
- Sort list (find middle + sort halves + merge)

### Complexity
| Operation | Time | Space |
|-----------|------|-------|
| Reorder | O(n) | O(1) |

---

## Pattern 8: Copy List with Random Pointer

### Signal
- "Deep copy list with arbitrary pointers"
- LC 138: Copy List with Random Pointer

### Node Definition

```java
class Node {
    int val;
    Node next, random;
    Node(int val) { this.val = val; }
}
```

### 8A: HashMap Approach

```java
public Node copyRandomList(Node head) {
    if (head == null) return null;
    
    Map<Node, Node> map = new HashMap<>();
    
    // Pass 1: Create all nodes
    Node curr = head;
    while (curr != null) {
        map.put(curr, new Node(curr.val));
        curr = curr.next;
    }
    
    // Pass 2: Wire next and random
    curr = head;
    while (curr != null) {
        map.get(curr).next = map.get(curr.next);
        map.get(curr).random = map.get(curr.random);
        curr = curr.next;
    }
    
    return map.get(head);
}
```

### 8B: Interleave Approach (O(1) Space)

```java
public Node copyRandomList(Node head) {
    if (head == null) return null;
    
    // Pass 1: Interleave copies — A→A'→B→B'→C→C'
    Node curr = head;
    while (curr != null) {
        Node copy = new Node(curr.val);
        copy.next = curr.next;
        curr.next = copy;
        curr = copy.next;
    }
    
    // Pass 2: Set random pointers
    curr = head;
    while (curr != null) {
        if (curr.random != null) {
            curr.next.random = curr.random.next; // copy's random = original's random's copy
        }
        curr = curr.next.next;
    }
    
    // Pass 3: Separate lists
    Node dummy = new Node(0);
    Node copyCurr = dummy;
    curr = head;
    while (curr != null) {
        copyCurr.next = curr.next;
        copyCurr = copyCurr.next;
        curr.next = copyCurr.next;
        curr = curr.next;
    }
    
    return dummy.next;
}
```

#### Visualization

```
Original:  A → B → C
           ↓       ↑ (random pointers)
           C       A

Pass 1 - Interleave:
  A → A' → B → B' → C → C'

Pass 2 - Random:
  A.random = C  → A'.random = C.next = C' ✓
  C.random = A  → C'.random = A.next = A' ✓

Pass 3 - Separate:
  Original: A → B → C (restored)
  Copy:     A'→ B'→ C' (with correct random pointers)
```

### Complexity
| Approach | Time | Space |
|----------|------|-------|
| HashMap | O(n) | O(n) |
| Interleave | O(n) | O(1) (excluding output) |

---

## Pattern 9: Add Two Numbers

### Signal
- "Numbers represented as linked lists, compute sum"
- Digits stored in reverse (LC 2) or forward (LC 445) order

### 9A: Reverse Order (LC 2)

```java
public ListNode addTwoNumbers(ListNode l1, ListNode l2) {
    ListNode dummy = new ListNode(0);
    ListNode curr = dummy;
    int carry = 0;
    
    while (l1 != null || l2 != null || carry != 0) {
        int sum = carry;
        if (l1 != null) { sum += l1.val; l1 = l1.next; }
        if (l2 != null) { sum += l2.val; l2 = l2.next; }
        
        carry = sum / 10;
        curr.next = new ListNode(sum % 10);
        curr = curr.next;
    }
    
    return dummy.next;
}
```

### 9B: Forward Order (LC 445)

```java
public ListNode addTwoNumbers(ListNode l1, ListNode l2) {
    // Use stacks to process from least significant digit
    Deque<Integer> s1 = new ArrayDeque<>(), s2 = new ArrayDeque<>();
    while (l1 != null) { s1.push(l1.val); l1 = l1.next; }
    while (l2 != null) { s2.push(l2.val); l2 = l2.next; }
    
    ListNode head = null;
    int carry = 0;
    
    while (!s1.isEmpty() || !s2.isEmpty() || carry != 0) {
        int sum = carry;
        if (!s1.isEmpty()) sum += s1.pop();
        if (!s2.isEmpty()) sum += s2.pop();
        
        carry = sum / 10;
        ListNode node = new ListNode(sum % 10);
        node.next = head;  // prepend
        head = node;
    }
    
    return head;
}
```

#### Visualization

```
Reverse order (LC 2):
  l1: 2 → 4 → 3  (represents 342)
  l2: 5 → 6 → 4  (represents 465)
  
  Step 1: 2+5+0 = 7, carry=0 → [7]
  Step 2: 4+6+0 = 10, carry=1 → [7→0]
  Step 3: 3+4+1 = 8, carry=0 → [7→0→8]
  
  Result: 7 → 0 → 8  (represents 807 = 342 + 465) ✓
```

### Key Details
- `while (l1 || l2 || carry)` — don't forget final carry
- Dummy head simplifies appending
- Forward order: stacks or reverse first

### Complexity
| Approach | Time | Space |
|----------|------|-------|
| Reverse order | O(max(m,n)) | O(max(m,n)) for result |
| Forward order (stack) | O(m+n) | O(m+n) |

---

## Master Complexity Summary

| Pattern | Time | Space | Key Technique |
|---------|------|-------|---------------|
| Floyd's Cycle | O(n) | O(1) | Two speeds |
| Reverse | O(n) | O(1) | prev/curr/next |
| Merge K Lists | O(N log k) | O(k) or O(log k) | Heap or D&C |
| Dummy Head | - | O(1) | Sentinel node |
| Nth from End | O(n) | O(1) | Fixed gap |
| Intersection | O(n+m) | O(1) | Path equalization |
| Reorder | O(n) | O(1) | Mid + Reverse + Merge |
| Copy Random | O(n) | O(1) or O(n) | Interleave or Map |
| Add Numbers | O(n) | O(n) | Carry propagation |

---

## Anti-Patterns and Common Bugs

1. **Forgetting to null-terminate** after cutting a list (e.g., `slow.next = null` in reorder)
2. **Not using dummy head** when head might be deleted → NullPointerException
3. **Off-by-one in gap technique** — for deletion, gap = n+1 (to land before target)
4. **Losing reference to next** during reversal — always save `next = curr.next` first
5. **Infinite loop in cycle problems** — ensure loop condition checks `fast && fast.next`
6. **Forgetting final carry** in addition — always include `carry != 0` in while condition
