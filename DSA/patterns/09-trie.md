# 09 - Trie Patterns

## Decision Flowchart

```
Need to process strings/prefixes?
│
├─ Prefix lookup / autocomplete? ──────────── Standard Trie / Autocomplete
│
├─ Pattern with wildcards ('.')? ───────────── Wildcard Search (DFS)
│
├─ Find multiple words in a grid? ─────────── Word Search II (Trie + Backtrack)
│
├─ Maximum XOR between numbers? ───────────── Binary Trie (XOR Trie)
│
├─ Count strings sharing prefix? ──────────── Prefix Count Trie
│
├─ Replace word with shortest prefix? ─────── Replace Words
│
└─ Longest word built char by char? ───────── Longest Word with All Prefixes
```

## Trie Node Structure Visualization

```
                    root (isEnd=false)
                   / |  \
                 a   b    c
                /    |     \
              p(1)   a      a
             / \     |      |
            p   r   d(2)   t(3)
            |   |
            l   t
            |
           e(4)

(1) "ap" prefix  (2) "bad" word  (3) "cat" word  (4) "apple" word

TrieNode:
┌──────────────────────────┐
│ children[26]  (or Map)   │
│ isEnd: boolean           │
│ word: String (optional)  │
│ prefixCount: int         │
└──────────────────────────┘
```

---

## Pattern 1: Standard Trie (Insert / Search / StartsWith)

### Signal
- Need O(L) insert/search where L = word length
- Prefix-based queries (startsWith, common prefix)
- Dictionary/vocabulary storage

### Template (Java)

```java
class Trie {
    private TrieNode root;

    class TrieNode {
        TrieNode[] children = new TrieNode[26];
        boolean isEnd = false;
    }

    public Trie() {
        root = new TrieNode();
    }

    public void insert(String word) {
        TrieNode node = root;
        for (char c : word.toCharArray()) {
            int idx = c - 'a';
            if (node.children[idx] == null)
                node.children[idx] = new TrieNode();
            node = node.children[idx];
        }
        node.isEnd = true;
    }

    public boolean search(String word) {
        TrieNode node = searchPrefix(word);
        return node != null && node.isEnd;
    }

    public boolean startsWith(String prefix) {
        return searchPrefix(prefix) != null;
    }

    private TrieNode searchPrefix(String prefix) {
        TrieNode node = root;
        for (char c : prefix.toCharArray()) {
            int idx = c - 'a';
            if (node.children[idx] == null) return null;
            node = node.children[idx];
        }
        return node;
    }
}
```

### Visualization

```
Insert: "app", "apple", "apt"

root
 └─ a
     └─ p
        ├─ p [end:"app"]
        │   └─ l
        │       └─ e [end:"apple"]
        └─ t [end:"apt"]

search("app")   → traverse a→p→p, isEnd=true  → TRUE
search("ap")    → traverse a→p,   isEnd=false → FALSE
startsWith("ap")→ traverse a→p,   node!=null  → TRUE
```

### Complexity
| Operation | Time | Space |
|-----------|------|-------|
| Insert | O(L) | O(L) worst case |
| Search | O(L) | O(1) |
| StartsWith | O(L) | O(1) |
| Total Space | — | O(N * L * 26) worst |

---

## Pattern 2: Wildcard Search with '.'

### Signal
- Search pattern can contain '.' matching any single character
- LC 211: Design Add and Search Words Data Structure

### Template (Java)

```java
class WordDictionary {
    TrieNode root = new TrieNode();

    class TrieNode {
        TrieNode[] children = new TrieNode[26];
        boolean isEnd = false;
    }

    public void addWord(String word) {
        TrieNode node = root;
        for (char c : word.toCharArray()) {
            int idx = c - 'a';
            if (node.children[idx] == null)
                node.children[idx] = new TrieNode();
            node = node.children[idx];
        }
        node.isEnd = true;
    }

    public boolean search(String word) {
        return dfs(word, 0, root);
    }

    private boolean dfs(String word, int i, TrieNode node) {
        if (node == null) return false;
        if (i == word.length()) return node.isEnd;

        char c = word.charAt(i);
        if (c == '.') {
            // Branch into ALL children
            for (TrieNode child : node.children) {
                if (dfs(word, i + 1, child)) return true;
            }
            return false;
        } else {
            return dfs(word, i + 1, node.children[c - 'a']);
        }
    }
}
```

### Visualization

```
Trie contains: "bad", "bag", "bat"

search("b.d"):
root → b → a → [branch on '.']
                 ├─ d [end] → MATCH! return true
                 ├─ g [end] → 'd'!='g' skip (but '.' so check isEnd for position)
                 └─ t [end] → skip

Actually with '.':
root → b → a → try ALL children at position 2:
                 d → i==3, isEnd=true → TRUE (short-circuit)
```

### Complexity
| Operation | Time | Space |
|-----------|------|-------|
| addWord | O(L) | O(L) |
| search (no dots) | O(L) | O(L) stack |
| search (all dots) | O(26^L) worst | O(L) stack |

---

## Pattern 3: Word Search II (Trie + Grid Backtracking)

### Signal
- Find ALL words from dictionary that exist in a 2D grid
- LC 212: multiple words, adjacent cells, no reuse per path
- Key insight: Trie lets you search all words simultaneously

### Template (Java)

```java
class Solution {
    int[][] dirs = {{0,1},{1,0},{0,-1},{-1,0}};
    List<String> result = new ArrayList<>();

    public List<String> findWords(char[][] board, String[] words) {
        // Build trie from dictionary
        TrieNode root = buildTrie(words);
        int m = board.length, n = board[0].length;

        for (int i = 0; i < m; i++)
            for (int j = 0; j < n; j++)
                backtrack(board, i, j, root);

        return result;
    }

    private void backtrack(char[][] board, int r, int c, TrieNode node) {
        if (r < 0 || r >= board.length || c < 0 || c >= board[0].length) return;

        char ch = board[r][c];
        if (ch == '#' || node.children[ch - 'a'] == null) return;

        node = node.children[ch - 'a'];

        if (node.word != null) {       // Found a word
            result.add(node.word);
            node.word = null;          // De-duplicate (pruning)
        }

        board[r][c] = '#';            // Mark visited
        for (int[] d : dirs)
            backtrack(board, r + d[0], c + d[1], node);
        board[r][c] = ch;             // Restore

        // CRITICAL PRUNING: remove leaf nodes to avoid dead-end traversals
        // (optional but improves runtime significantly)
    }

    private TrieNode buildTrie(String[] words) {
        TrieNode root = new TrieNode();
        for (String w : words) {
            TrieNode node = root;
            for (char c : w.toCharArray()) {
                int idx = c - 'a';
                if (node.children[idx] == null)
                    node.children[idx] = new TrieNode();
                node = node.children[idx];
            }
            node.word = w;  // Store full word at terminal node
        }
        return root;
    }

    class TrieNode {
        TrieNode[] children = new TrieNode[26];
        String word = null;  // Non-null = terminal
    }
}
```

### Visualization

```
Board:          Dictionary: ["oath","pea","eat","rain"]
o a a n
e t a e         Trie:
i h i r              root
h e l p             / |  \
                   o  e   r
                   |  |   |
                   a  a   a
                   |  |   |
                   t  t*  i
                   |      |
                   h*     n*
                   
DFS from (0,0)='o': o→a→t→h → "oath" found!
DFS from (1,1)='t': no 't' child at root → skip
DFS from (1,0)='e': e→a→t → "eat" found!
```

### Complexity
| | Time | Space |
|--|------|-------|
| Build Trie | O(W * L) | O(W * L) |
| Backtracking | O(M * N * 4^L) | O(L) recursion |
| Total | O(W*L + M*N*4^L) | O(W * L) |

W = num words, L = max word length, M*N = grid size

---

## Pattern 4: XOR Trie / Binary Trie

### Signal
- Maximum XOR of two numbers in array
- LC 421: For each number, greedily pick opposite bits
- Bitwise operations + prefix structure

### Template (Java)

```java
class Solution {
    static final int MAX_BIT = 30; // for values up to 10^9

    class TrieNode {
        TrieNode[] children = new TrieNode[2]; // 0 and 1
    }

    public int findMaximumXOR(int[] nums) {
        TrieNode root = new TrieNode();

        // Insert all numbers
        for (int num : nums) {
            TrieNode node = root;
            for (int i = MAX_BIT; i >= 0; i--) {
                int bit = (num >> i) & 1;
                if (node.children[bit] == null)
                    node.children[bit] = new TrieNode();
                node = node.children[bit];
            }
        }

        // For each number, greedily find max XOR partner
        int maxXor = 0;
        for (int num : nums) {
            TrieNode node = root;
            int xor = 0;
            for (int i = MAX_BIT; i >= 0; i--) {
                int bit = (num >> i) & 1;
                int want = 1 - bit;  // Want opposite bit for max XOR
                if (node.children[want] != null) {
                    xor |= (1 << i);
                    node = node.children[want];
                } else {
                    node = node.children[bit];
                }
            }
            maxXor = Math.max(maxXor, xor);
        }
        return maxXor;
    }
}
```

### Visualization

```
nums = [3, 10, 5, 25, 2]

Binary (5 bits):  3=00011, 10=01010, 5=00101, 25=11001, 2=00010

Binary Trie (from MSB to LSB):
         root
        /    \
       0      1
      / \      \
     0   1      1
    / \   \      \
   0   1   0      0
  / \   \   \      \
 1   0   0   1      0
 |   |   |   |      |
 1   1   1   0      1
 ↑   ↑   ↑   ↑      ↑
 3   2   5  10     25

Query num=3 (00011), greedily pick opposite:
  bit=0 → want 1 → EXISTS (go right)  → xor bit set
  bit=0 → want 1 → EXISTS (go right)  → xor bit set
  bit=0 → want 1 → NOT exists → go 0
  bit=1 → want 0 → EXISTS (go left)   → xor bit set
  bit=1 → want 0 → EXISTS             → xor bit set
  XOR = 11110₂ = 30  (3 XOR 25 = 28... actual max is 25 XOR 5 = 28)

Max XOR = 28
```

### Complexity
| Operation | Time | Space |
|-----------|------|-------|
| Insert | O(B) per number | O(N * B) |
| Query | O(B) per number | O(1) |
| Total | O(N * B) | O(N * B) |

B = number of bits (typically 30-31)

---

## Pattern 5: Autocomplete / Search Suggestions

### Signal
- Return top-K suggestions for a given prefix
- LC 1268: Search Suggestions System
- Type-ahead / autocomplete systems

### Template (Java)

```java
class AutocompleteSystem {
    class TrieNode {
        TrieNode[] children = new TrieNode[26];
        List<String> suggestions = new ArrayList<>(); // top words through this node
    }

    TrieNode root = new TrieNode();
    int K = 3; // top-K suggestions

    public void insert(String word) {
        TrieNode node = root;
        for (char c : word.toCharArray()) {
            int idx = c - 'a';
            if (node.children[idx] == null)
                node.children[idx] = new TrieNode();
            node = node.children[idx];
            // Maintain sorted top-K at each node
            node.suggestions.add(word);
            Collections.sort(node.suggestions);
            if (node.suggestions.size() > K)
                node.suggestions.remove(node.suggestions.size() - 1);
        }
    }

    // LC 1268: Return suggestions after each character typed
    public List<List<String>> suggestedProducts(String[] products, String search) {
        Arrays.sort(products);
        for (String p : products) insert(p);

        List<List<String>> result = new ArrayList<>();
        TrieNode node = root;
        boolean dead = false;

        for (char c : search.toCharArray()) {
            if (dead || node.children[c - 'a'] == null) {
                dead = true;
                result.add(new ArrayList<>());
            } else {
                node = node.children[c - 'a'];
                result.add(node.suggestions);
            }
        }
        return result;
    }
}
```

### Visualization

```
Products: ["mobile","mouse","moneypot","monitor","mousepad"]
searchWord: "mouse"

After 'm': [mobile, moneypot, monitor]  (top 3 lex)
After 'o': [mobile, moneypot, monitor]
After 'u': [mouse, mousepad]
After 's': [mouse, mousepad]
After 'e': [mouse, mousepad]

Trie with suggestions stored at each node:
root
 └─ m → [mobile, moneypot, monitor]
     └─ o → [mobile, moneypot, monitor]
        ├─ b → [mobile]
        ├─ n → [moneypot, monitor]
        └─ u → [mouse, mousepad]
            └─ s → [mouse, mousepad]
                └─ e → [mouse, mousepad]
```

### Variants
- **DFS-based**: Don't store at nodes; DFS from prefix node collecting words
- **Priority Queue**: For frequency-weighted suggestions (not just lexicographic)
- **Bounded DFS**: Stop after K results found

### Complexity
| Operation | Time | Space |
|-----------|------|-------|
| Insert | O(L * K) (sort at each level) | O(N * L * K) |
| Query per char | O(1) with pre-stored | — |
| DFS approach query | O(subtree size) | O(L) stack |

---

## Pattern 6: Prefix Count / Sum of Prefix Scores

### Signal
- Count how many words share each prefix
- LC 2416: Sum of Prefix Scores of Strings
- "How many words start with this prefix?"

### Template (Java)

```java
class Solution {
    class TrieNode {
        TrieNode[] children = new TrieNode[26];
        int prefixCount = 0;  // Words passing through this node
    }

    public int[] sumPrefixScores(String[] words) {
        TrieNode root = new TrieNode();

        // Insert all words, incrementing prefixCount
        for (String word : words) {
            TrieNode node = root;
            for (char c : word.toCharArray()) {
                int idx = c - 'a';
                if (node.children[idx] == null)
                    node.children[idx] = new TrieNode();
                node = node.children[idx];
                node.prefixCount++;
            }
        }

        // For each word, sum up prefixCount along its path
        int[] result = new int[words.length];
        for (int i = 0; i < words.length; i++) {
            TrieNode node = root;
            int score = 0;
            for (char c : words[i].toCharArray()) {
                node = node.children[c - 'a'];
                score += node.prefixCount;
            }
            result[i] = score;
        }
        return result;
    }
}
```

### Visualization

```
words = ["abc", "ab", "abcd"]

Insert phase (prefixCount at each node):
root
 └─ a (3)       ← 3 words pass through 'a'
     └─ b (3)   ← 3 words pass through 'ab'
         └─ c (2) ← 2 words pass through 'abc'
             └─ d (1)

Score for "abc":  count('a') + count('ab') + count('abc') = 3 + 3 + 2 = 8
Score for "ab":   count('a') + count('ab') = 3 + 3 = 6
Score for "abcd": 3 + 3 + 2 + 1 = 9
```

### Complexity
| Operation | Time | Space |
|-----------|------|-------|
| Build | O(N * L) | O(N * L) |
| Query all | O(N * L) | O(1) extra |

---

## Pattern 7: Replace Words (Shortest Prefix in Dictionary)

### Signal
- Given dictionary of roots, replace words with their shortest root
- LC 648: Replace Words
- Key: stop at first `isEnd` during traversal

### Template (Java)

```java
class Solution {
    class TrieNode {
        TrieNode[] children = new TrieNode[26];
        boolean isEnd = false;
    }

    public String replaceWords(List<String> dictionary, String sentence) {
        TrieNode root = new TrieNode();

        // Build trie from dictionary
        for (String word : dictionary) {
            TrieNode node = root;
            for (char c : word.toCharArray()) {
                int idx = c - 'a';
                if (node.children[idx] == null)
                    node.children[idx] = new TrieNode();
                node = node.children[idx];
            }
            node.isEnd = true;
        }

        // Replace each word with shortest prefix
        StringBuilder sb = new StringBuilder();
        for (String word : sentence.split(" ")) {
            if (sb.length() > 0) sb.append(' ');
            sb.append(getShortestRoot(root, word));
        }
        return sb.toString();
    }

    private String getShortestRoot(TrieNode root, String word) {
        TrieNode node = root;
        for (int i = 0; i < word.length(); i++) {
            int idx = word.charAt(i) - 'a';
            if (node.children[idx] == null) break; // No prefix found
            node = node.children[idx];
            if (node.isEnd) return word.substring(0, i + 1); // SHORTEST prefix
        }
        return word; // No root found, keep original
    }
}
```

### Visualization

```
dictionary = ["cat", "bat", "rat", "ca"]
sentence = "the cattle was rattled by the battery"

Trie:
root
 ├─ c─a [end:"ca"]    ← "ca" is shorter than "cat"
 │    └─ t [end:"cat"]
 ├─ b─a─t [end:"bat"]
 └─ r─a─t [end:"rat"]

"cattle" → traverse c→a → isEnd! → "ca"  (shortest wins)
"rattled" → traverse r→a→t → isEnd! → "rat"
"battery" → traverse b→a→t → isEnd! → "bat"
"the"     → no 't' child → keep "the"

Result: "the ca was rat by the bat"
```

### Complexity
| Operation | Time | Space |
|-----------|------|-------|
| Build | O(D * L) | O(D * L) |
| Replace | O(S * L) per word | O(1) extra |

D = dictionary size, S = sentence word count, L = max word length

---

## Pattern 8: Longest Word with All Prefixes

### Signal
- Find longest word where every prefix is also a valid word
- LC 720: Longest Word in Dictionary
- Key: BFS/DFS only following nodes where `isEnd=true`

### Template (Java)

```java
class Solution {
    class TrieNode {
        TrieNode[] children = new TrieNode[26];
        boolean isEnd = false;
        String word = "";
    }

    public String longestWord(String[] words) {
        TrieNode root = new TrieNode();

        // Build trie
        for (String w : words) {
            TrieNode node = root;
            for (char c : w.toCharArray()) {
                int idx = c - 'a';
                if (node.children[idx] == null)
                    node.children[idx] = new TrieNode();
                node = node.children[idx];
            }
            node.isEnd = true;
            node.word = w;
        }

        // BFS: only traverse children that are end-of-word
        String result = "";
        Queue<TrieNode> queue = new LinkedList<>();
        queue.offer(root);

        while (!queue.isEmpty()) {
            TrieNode node = queue.poll();
            for (TrieNode child : node.children) {
                if (child != null && child.isEnd) {
                    // This child represents a valid word — can extend
                    if (child.word.length() > result.length() ||
                        (child.word.length() == result.length() &&
                         child.word.compareTo(result) < 0)) {
                        result = child.word;
                    }
                    queue.offer(child);
                }
            }
        }
        return result;
    }
}
```

### Visualization

```
words = ["a","banana","app","appl","ap","apply","apple"]

Trie (only paths where every prefix is a word):
root
 └─ a [end] ✓
     └─ p [end:"ap"] ✓
         └─ p [end:"app"] ✓
             └─ l [end:"appl"] ✓
                 ├─ e [end:"apple"] ✓  ← length 5
                 └─ y [end:"apply"] ✓  ← length 5, but "apple" < "apply"

"banana" → 'b' is end? NO → cannot build "banana" incrementally
Answer: "apple" (longest, lexicographically smallest among ties)
```

### Complexity
| Operation | Time | Space |
|-----------|------|-------|
| Build | O(N * L) | O(N * L) |
| BFS | O(N * L) | O(N) queue |

---

## Pattern 9: Trie vs HashMap vs TreeMap

| Criteria | Trie | HashMap | TreeMap |
|----------|------|---------|---------|
| **Prefix queries** | O(P) native | O(N) scan all keys | O(log N + K) with subMap |
| **Exact lookup** | O(L) | O(L) hash + O(1) amortized | O(L * log N) |
| **Wildcard search** | O(26^dots * L) | O(N * L) brute force | O(N * L) brute force |
| **Sorted iteration** | DFS = lexicographic | Not sorted | Natural order |
| **Space** | O(N * L * SIGMA) | O(N * L) | O(N * L) |
| **Insert** | O(L) | O(L) amortized | O(L * log N) |
| **Count by prefix** | O(P) with prefixCount | O(N) scan | O(log N) with subMap |
| **Best for** | Prefix-heavy, autocomplete, XOR | Exact match, frequency | Range queries, floor/ceiling |

### When to Choose

```
┌─────────────────────────────────────────────────────────┐
│ Choose TRIE when:                                       │
│  • Multiple prefix queries                              │
│  • Wildcard patterns                                    │
│  • Need to search all words simultaneously (Word Search)│
│  • XOR optimization (binary trie)                       │
│  • Autocomplete / suggestions                           │
│                                                         │
│ Choose HASHMAP when:                                    │
│  • Only exact lookups needed                            │
│  • Frequency counting                                   │
│  • Space is critical (trie has 26x overhead)            │
│                                                         │
│ Choose TREEMAP when:                                    │
│  • Need sorted order + range queries                    │
│  • Floor/ceiling operations                             │
│  • No prefix-specific operations                        │
└─────────────────────────────────────────────────────────┘
```

---

## Summary Cheat Sheet

| # | Pattern | Key Insight | LC Examples |
|---|---------|-------------|-------------|
| 1 | Standard Trie | Array of children + isEnd flag | 208 |
| 2 | Wildcard Search | DFS branching on '.' across all children | 211 |
| 3 | Word Search II | Build trie from words, DFS grid, prune leaves | 212 |
| 4 | XOR / Binary Trie | 2 children (0/1), greedily pick opposite bit | 421 |
| 5 | Autocomplete | Store top-K at each node or DFS from prefix | 1268, 642 |
| 6 | Prefix Count | Increment counter at each node during insert | 2416 |
| 7 | Replace Words | Stop at first isEnd = shortest prefix match | 648 |
| 8 | Longest Word | BFS/DFS only through isEnd nodes | 720 |

### Common Optimizations
- **Pruning in Word Search II**: Remove leaf nodes after finding word (prevents re-traversal)
- **Compressed Trie (Radix Tree)**: Merge single-child chains for space efficiency
- **HashMap children**: Use `Map<Character, TrieNode>` when alphabet is large (Unicode)
- **Bit manipulation in XOR Trie**: Process from MSB to LSB for greedy maximization
