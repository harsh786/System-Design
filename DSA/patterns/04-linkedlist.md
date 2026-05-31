# Linked List - Pattern Guide

---

## Pattern Recognition Signals

| Signal | Pattern |
|--------|---------|
| Detect cycle / find cycle start | Floyd's Fast/Slow |
| Find middle node | Fast/Slow |
| Reverse list or section | Iterative 3-pointer |
| Remove nth from end | Two pointers with gap |
| Merge sorted lists | Dummy + compare heads |
| Head might change | Dummy node |
| Reorder / interleave | Find middle + reverse + merge |
| Intersection of two lists | Length diff or two-pointer cycle |

---

## Pattern 1: Fast/Slow Pointer (Floyd's Algorithm)

**When:** Cycle detection, find cycle start, find middle node.

### Cycle Detection
```java
ListNode slow = head, fast = head;
while (fast != null && fast.next != null) {
    slow = slow.next;
    fast = fast.next.next;
    if (slow == fast) return true;  // CYCLE!
}
return false;  // no cycle
```

### Find Cycle Start
```java
// After detection (slow == fast):
slow = head;
while (slow != fast) {
    slow = slow.next;
    fast = fast.next;  // both move ONE step now
}
return slow;  // cycle entry point
```

### Mathematical Proof (Why It Works)
```
Let:
  F = distance from head to cycle start
  C = cycle length
  a = distance from cycle start to meeting point

When they meet:
  slow traveled: F + a
  fast traveled: F + a + nC (some complete loops)
  fast = 2 * slow → F + a + nC = 2(F + a)
  → nC = F + a → F = nC - a

After reset slow to head:
  slow travels F steps to reach cycle start
  fast travels F = nC - a steps from meeting point
  = exactly back to cycle start!
```

### Find Middle
```java
ListNode slow = head, fast = head;
while (fast != null && fast.next != null) {
    slow = slow.next;
    fast = fast.next.next;
}
return slow;  // middle (or left-middle for even-length)
```

```
Odd:  1 → 2 → 3 → 4 → 5        slow stops at 3 ✓
Even: 1 → 2 → 3 → 4 → 5 → 6   slow stops at 4 (right-middle)
For left-middle: use while (fast.next != null && fast.next.next != null)
```

---

## Pattern 2: Reverse Linked List

**When:** Reverse entire list, reverse subsection, check palindrome.

### Iterative (Full Reverse)
```java
ListNode prev = null, curr = head;
while (curr != null) {
    ListNode next = curr.next;
    curr.next = prev;      // flip arrow
    prev = curr;           // advance prev
    curr = next;           // advance curr
}
return prev;  // new head
```

```
Step by step:
  null ← 1    2 → 3 → 4       prev=1, curr=2
  null ← 1 ← 2    3 → 4       prev=2, curr=3
  null ← 1 ← 2 ← 3    4       prev=3, curr=4
  null ← 1 ← 2 ← 3 ← 4       prev=4, curr=null → return 4
```

### Reverse Between Positions [left, right]
```java
ListNode dummy = new ListNode(0, head);
ListNode pre = dummy;
for (int i = 1; i < left; i++) pre = pre.next;  // node before left

ListNode curr = pre.next;
for (int i = 0; i < right - left; i++) {
    ListNode next = curr.next;
    curr.next = next.next;       // skip next
    next.next = pre.next;        // next points to sublist head
    pre.next = next;             // pre points to next (new sublist head)
}
return dummy.next;
```

### Reverse in K-Groups
```java
ListNode dummy = new ListNode(0, head);
ListNode groupPrev = dummy;

while (true) {
    ListNode kth = getKth(groupPrev, k);
    if (kth == null) break;
    ListNode groupNext = kth.next;
    
    // Reverse group
    ListNode prev = groupNext, curr = groupPrev.next;
    while (curr != groupNext) {
        ListNode next = curr.next;
        curr.next = prev;
        prev = curr;
        curr = next;
    }
    
    ListNode tmp = groupPrev.next;
    groupPrev.next = kth;
    groupPrev = tmp;
}
```

---

## Pattern 3: Merge Sorted Lists

### Merge Two
```java
ListNode dummy = new ListNode(0), tail = dummy;
while (l1 != null && l2 != null) {
    if (l1.val <= l2.val) { tail.next = l1; l1 = l1.next; }
    else { tail.next = l2; l2 = l2.next; }
    tail = tail.next;
}
tail.next = (l1 != null) ? l1 : l2;
return dummy.next;
```

### Merge K Sorted Lists

**Approach 1: Divide and Conquer** — O(N log k)
```java
ListNode mergeKLists(ListNode[] lists, int lo, int hi) {
    if (lo == hi) return lists[lo];
    int mid = (lo + hi) / 2;
    ListNode left = mergeKLists(lists, lo, mid);
    ListNode right = mergeKLists(lists, mid + 1, hi);
    return mergeTwoLists(left, right);
}
```

**Approach 2: Min Heap** — O(N log k)
```java
PriorityQueue<ListNode> pq = new PriorityQueue<>((a,b) -> a.val - b.val);
for (ListNode l : lists) if (l != null) pq.offer(l);
ListNode dummy = new ListNode(0), tail = dummy;
while (!pq.isEmpty()) {
    ListNode node = pq.poll();
    tail.next = node;
    tail = tail.next;
    if (node.next != null) pq.offer(node.next);
}
return dummy.next;
```

---

## Pattern 4: Dummy Head Technique

**When:** Head might be removed or changed. Eliminates head-specific edge cases.

```java
ListNode dummy = new ListNode(0);
dummy.next = head;
// ... operations using prev starting at dummy ...
return dummy.next;  // true head
```

**Always use when:**
- Removing nodes (head might be removed)
- Partitioning (new list might have different head)
- Merging (choosing between two heads)

---

## Pattern 5: Nth from End (Two-Pointer Gap)

**When:** Access or remove nth node from end without knowing length.

```java
ListNode dummy = new ListNode(0, head);
ListNode fast = dummy, slow = dummy;

// Create gap of n+1
for (int i = 0; i <= n; i++) fast = fast.next;

// Move both until fast hits end
while (fast != null) {
    slow = slow.next;
    fast = fast.next;
}

// slow is now at (n+1)th from end → slow.next is target
slow.next = slow.next.next;  // remove nth from end
return dummy.next;
```

```
n=2: Remove 2nd from end of [1,2,3,4,5]

gap of 3: fast at node 3
  slow: dummy → 1 → 2 → 3
  fast:  3    → 4 → 5 → null
  
slow.next = 4 → skip it → [1,2,3,5]
```

---

## Pattern 6: Intersection Detection

**When:** Find node where two lists converge.

```java
ListNode a = headA, b = headB;
while (a != b) {
    a = (a != null) ? a.next : headB;
    b = (b != null) ? b.next : headA;
}
return a;  // intersection or null (both reach null together)
```

### Why It Works
```
List A: a1 → a2 → c1 → c2 → c3       (length = 5)
List B: b1 → b2 → b3 → c1 → c2 → c3  (length = 6)

Pointer a travels: a1,a2,c1,c2,c3, then b1,b2,b3,c1 (meets!)
Pointer b travels: b1,b2,b3,c1,c2,c3, then a1,a2,c1 (meets!)

Both travel lenA + lenB steps → meet at intersection
```

---

## Pattern 7: Reorder / Rearrange

**When:** Interleave halves, convert L0→Ln→L1→Ln-1→...

### Reorder List (L0→Ln→L1→Ln-1)
```java
// Step 1: Find middle
ListNode slow = head, fast = head;
while (fast.next != null && fast.next.next != null) {
    slow = slow.next;
    fast = fast.next.next;
}

// Step 2: Reverse second half
ListNode second = reverse(slow.next);
slow.next = null;

// Step 3: Interleave
ListNode first = head;
while (second != null) {
    ListNode tmp1 = first.next, tmp2 = second.next;
    first.next = second;
    second.next = tmp1;
    first = tmp1;
    second = tmp2;
}
```

```
1 → 2 → 3 → 4 → 5
Step 1: first = 1→2→3, second = 4→5
Step 2: reverse second = 5→4
Step 3: interleave = 1→5→2→4→3
```

### Palindrome Check (Same Technique)
```
1. Find middle
2. Reverse second half
3. Compare first half with reversed second half
4. (Optional) Restore list
```

---

## Pattern 8: Copy List with Random Pointer

### Approach 1: HashMap — O(n) time, O(n) space
```java
Map<Node, Node> map = new HashMap<>();
Node curr = head;
while (curr != null) { map.put(curr, new Node(curr.val)); curr = curr.next; }
curr = head;
while (curr != null) {
    map.get(curr).next = map.get(curr.next);
    map.get(curr).random = map.get(curr.random);
    curr = curr.next;
}
return map.get(head);
```

### Approach 2: Interleave — O(n) time, O(1) space
```
Original: A → B → C
Step 1 (interleave): A → A' → B → B' → C → C'
Step 2 (wire random): A'.random = A.random.next
Step 3 (separate): restore original + extract copy
```

---

## Pattern 9: Add Two Numbers (Digit Lists)

```java
ListNode dummy = new ListNode(0), curr = dummy;
int carry = 0;
while (l1 != null || l2 != null || carry > 0) {
    int sum = carry;
    if (l1 != null) { sum += l1.val; l1 = l1.next; }
    if (l2 != null) { sum += l2.val; l2 = l2.next; }
    curr.next = new ListNode(sum % 10);
    carry = sum / 10;
    curr = curr.next;
}
return dummy.next;
```

---

## Summary Flowchart

```
Linked List Problem?
│
├─ Cycle? ─────────────────→ Floyd's fast/slow
│
├─ Reverse? ───────────────→ Iterative 3-pointer (prev/curr/next)
│
├─ Merge sorted? ──────────→ Dummy + compare heads (or heap for K)
│
├─ Remove/access from end? → Two-pointer gap of N
│
├─ Intersection? ──────────→ Two pointers, switch lists at end
│
├─ Reorder/palindrome? ────→ Find middle + reverse + merge
│
├─ Head might change? ─────→ Dummy node (use by default)
│
└─ Copy complex structure? → HashMap (easy) or Interleave (O(1) space)
```
