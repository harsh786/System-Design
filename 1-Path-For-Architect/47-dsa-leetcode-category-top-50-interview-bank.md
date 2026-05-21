# DSA Interview Questions By LeetCode Category For Architect Interviews

Purpose: provide a complete, concrete DSA practice bank for senior backend, staff, principal, and architect interviews. Each category uses category-specific named LeetCode-style or canonical interview problems, not generic filler prompts and not unrelated cross-category padding.

Use this with `04-dsa-algorithms-production-patterns.md`. That file explains the roadmap and production patterns; this file gives up to 50 category-relevant problems for every category shown in the LeetCode-style category map.

Important note: some narrow tags in the screenshot have fewer than 50 widely known public LeetCode-tagged problems, for example Shell, Eulerian Circuit, Rejection Sampling, and Biconnected Component. Those sections intentionally have fewer than 50 entries rather than pulling unrelated array/string problems just to fill space.

How to use:

1. Solve 5-10 problems per category before moving to the next category.
2. For each solution, explain brute force, optimized approach, complexity, edge cases, and proof of correctness.
3. For architect interviews, connect the pattern to a real system component: cache, scheduler, queue, index, search, stream processor, rate limiter, storage engine, workflow engine, or graph service.
4. If a problem appears in multiple categories, solve it once deeply, then revisit it through the category-specific lens.

Total coverage: 71 categories with up to 50 category-specific problems each; narrow categories are intentionally shorter.

## Category Coverage Map

| # | Category | Focus |
|---:|---|---|
| 1 | Array | Indexing, in-place mutation, prefix state, interval reasoning, and memory-aware linear scans |
| 2 | String | Character frequency, parsing, sliding windows, encoding, and immutable data trade-offs |
| 3 | Hash Table | O(1) lookup, counting, deduplication, grouping, key design, and collision-aware reasoning |
| 4 | Math | Arithmetic invariants, modular arithmetic, geometry, combinatorics, and numeric edge cases |
| 5 | Dynamic Programming | State definition, recurrence, transitions, memoization, tabulation, and optimization |
| 6 | Sorting | Ordering, custom comparators, intervals, stability, external sorting, and ranking |
| 7 | Greedy | Local choice proof, exchange argument, sorting plus choice, and counterexamples |
| 8 | Binary Search | Monotonic predicates, rotated arrays, answer-space search, and boundary correctness |
| 9 | Depth-First Search | Recursive traversal, state marking, backtracking, cycle detection, and graph/tree exploration |
| 10 | Database | SQL joins, grouping, ranking, window functions, deduplication, and query correctness |
| 11 | Bit Manipulation | XOR, masks, shifts, subsets, parity, integer representation, and overflow |
| 12 | Matrix | Grid traversal, coordinate transforms, BFS/DFS, prefix matrices, and in-place marking |
| 13 | Tree | Recursive structure, traversal, LCA, serialization, balanced trees, and subtree invariants |
| 14 | Breadth-First Search | Shortest unweighted paths, levels, multi-source expansion, and queue discipline |
| 15 | Two Pointers | Sorted scans, partitioning, palindromes, fast/slow pointers, and in-place movement |
| 16 | Prefix Sum | Cumulative state, range queries, subarray counts, difference arrays, and 2D sums |
| 17 | Heap (Priority Queue) | Top-K, streaming order, scheduling, k-way merge, and priority updates |
| 18 | Simulation | State machines, event processing, rules implementation, and correctness by invariants |
| 19 | Counting | Frequency arrays, histograms, buckets, bounded domains, and count-based optimization |
| 20 | Graph Theory | Graph modeling, traversal, connectivity, cycles, paths, and representation trade-offs |
| 21 | Binary Tree | Traversal, recursion, path state, subtree aggregation, and structural transformations |
| 22 | Stack | Nested state, expression parsing, monotonic patterns, undo semantics, and validation |
| 23 | Sliding Window | Contiguous window invariants, frequency maps, two-boundary movement, and amortized O(n) |
| 24 | Enumeration | Systematic case generation, pruning, bitmask enumeration, and complexity control |
| 25 | Design | API contracts, state ownership, complexity guarantees, cache/data-structure composition, and edge cases |
| 26 | Backtracking | Search tree, choices, constraints, pruning, duplicates, and restoration of state |
| 27 | Union-Find | Connectivity, path compression, union by rank, dynamic components, and cycle detection |
| 28 | Number Theory | GCD/LCM, primes, modular arithmetic, divisibility, and integer constraints |
| 29 | Linked List | Pointer mutation, sentinel nodes, cycle detection, reversal, and memory-safe updates |
| 30 | Segment Tree | Range queries, range updates, lazy propagation, and merge functions |
| 31 | Ordered Set | Balanced BST operations, floor/ceiling, rank, interval queries, and sliding order statistics |
| 32 | Monotonic Stack | Next greater/smaller, histogram areas, span, contribution counting, and amortized proof |
| 33 | Divide and Conquer | Recursive decomposition, merge logic, recurrence analysis, and parallelizable thinking |
| 34 | Combinatorics | Counting arrangements, binomial coefficients, inclusion-exclusion, and modular counting |
| 35 | Trie | Prefix tree modeling, word search, autocomplete, wildcard search, and compressed storage trade-offs |
| 36 | Bitmask | Subset states, compressed DP, visited masks, permissions, and exponential-state control |
| 37 | Queue | FIFO processing, BFS, rate windows, buffering, and producer-consumer style reasoning |
| 38 | Recursion | Base cases, recursion tree, call stack, divide/merge, and iterative conversion |
| 39 | Geometry | Coordinates, distance, orientation, line sweep, convexity, and precision issues |
| 40 | Binary Indexed Tree | Fenwick tree prefix queries, point updates, coordinate compression, and inversion counting |
| 41 | Hash Function | Rolling hash, canonicalization, collision risk, dedupe, and checksum-style reasoning |
| 42 | Memoization | Top-down DP, cache keys, overlapping subproblems, invalid states, and memory control |
| 43 | Binary Search Tree | Ordered tree invariants, range search, insert/delete, balancing assumptions, and iterators |
| 44 | Topological Sort | DAG ordering, dependency resolution, cycle detection, and scheduling |
| 45 | Shortest Path | BFS, Dijkstra, Bellman-Ford, Floyd-Warshall, state-expanded graphs, and weights |
| 46 | String Matching | KMP, Z algorithm, trie, suffix structures, wildcard matching, and pattern preprocessing |
| 47 | Rolling Hash | Polynomial hashing, Rabin-Karp, collision handling, double hashing, and substring equality |
| 48 | Game Theory | Winning states, minimax, DP on games, Sprague-Grundy ideas, and adversarial reasoning |
| 49 | Interactive | Query strategy, binary search with feedback, invariant maintenance, and limited-call optimization |
| 50 | Data Stream | Online algorithms, heaps, sketches, windows, approximations, and memory bounds |
| 51 | Monotonic Queue | Deque invariants, sliding max/min, DP optimization, and amortized O(1) updates |
| 52 | Brainteaser | Invariants, paradoxes, probability, adversarial constraints, and clear communication |
| 53 | Doubly-Linked List | O(1) removal/insertion, cache design, sentinel nodes, and pointer consistency |
| 54 | Merge Sort | Stable divide-and-conquer sorting, inversion counting, linked-list sorting, and external merge |
| 55 | Randomized | Random sampling, expected complexity, shuffling, randomized sets, and adversarial input resistance |
| 56 | Counting Sort | Bounded-domain sorting, frequency accumulation, stable placement, and memory trade-offs |
| 57 | Iterator | Lazy traversal, flattening, peeking, nested structures, and fail-fast semantics |
| 58 | Concurrency | Thread coordination, synchronization, blocking queues, race prevention, and correctness under interleavings |
| 59 | Suffix Array | Suffix ordering, LCP, substring search, repeated substrings, and string indexing |
| 60 | Quickselect | Selection, partitioning, expected linear time, pivot choice, and worst-case risk |
| 61 | Sweep Line | Events, active set, interval overlap, geometry intersections, and time-ordered state |
| 62 | Probability and Statistics | Expected value, random processes, distributions, sampling, and estimation |
| 63 | Minimum Spanning Tree | Kruskal, Prim, cut/cycle properties, DSU, and network design analogies |
| 64 | Bucket Sort | Distribution-aware sorting, bucket design, hashing/ranges, and linear-time assumptions |
| 65 | Shell | Gap-based insertion sorting, diminishing increments, cache behavior, and algorithm comparison |
| 66 | Reservoir Sampling | Uniform streaming sample, unknown length, weighted sampling, and proof of probability |
| 67 | Eulerian Circuit | In/out degree conditions, Hierholzer, itinerary reconstruction, and edge-once traversal |
| 68 | Radix Sort | Digit-wise sorting, stable counting sort, integer/string keys, and linear-time constraints |
| 69 | Strongly Connected Component | Kosaraju, Tarjan, condensation DAG, cycle groups, and dependency analysis |
| 70 | Rejection Sampling | Sampling from constrained distributions, acceptance probability, bias, and efficiency |
| 71 | Biconnected Component | Articulation points, bridges, low-link values, resilience, and block-cut trees |

## Architect Answer Bar

For every problem, your answer should include:

1. Pattern recognition: why this is the right category.
2. Brute force and why it fails at scale.
3. Optimal algorithm and invariant.
4. Time and space complexity with realistic constants.
5. Edge cases and failure modes.
6. Production analogy, such as cache eviction, stream aggregation, scheduling, dependency graphs, indexing, or routing.

## 1. Array - Top 50

Architect focus: Indexing, in-place mutation, prefix state, interval reasoning, and memory-aware linear scans.

1. Two Sum
2. Best Time to Buy and Sell Stock
3. Contains Duplicate
4. Product of Array Except Self
5. Maximum Subarray
6. Maximum Product Subarray
7. Find Minimum in Rotated Sorted Array
8. Search in Rotated Sorted Array
9. 3Sum
10. Container With Most Water
11. Next Permutation
12. Merge Intervals
13. Sort Colors
14. Subarray Sum Equals K
15. Rotate Array
16. Trapping Rain Water
17. First Missing Positive
18. Longest Consecutive Sequence
19. 4Sum
20. Median of Two Sorted Arrays
21. Majority Element
22. Missing Number
23. Move Zeroes
24. Merge Sorted Array
25. Set Matrix Zeroes
26. Insert Interval
27. Non-overlapping Intervals
28. Find All Duplicates in an Array
29. Find the Duplicate Number
30. Maximum Gap
31. Jump Game
32. Jump Game II
33. Candy
34. Gas Station
35. H-Index
36. Find Pivot Index
37. Squares of a Sorted Array
38. Can Place Flowers
39. Max Consecutive Ones
40. Maximum Average Subarray I
41. Degree of an Array
42. Shortest Unsorted Continuous Subarray
43. Third Maximum Number
44. Array Partition
45. Subarray Product Less Than K
46. Minimum Size Subarray Sum
47. Find All Numbers Disappeared in an Array
48. Summary Ranges
49. Pascal Triangle
50. Pascal Triangle II

## 2. String - Top 50

Architect focus: Character frequency, parsing, sliding windows, encoding, and immutable data trade-offs.

1. Valid Anagram
2. Group Anagrams
3. Longest Substring Without Repeating Characters
4. Longest Repeating Character Replacement
5. Minimum Window Substring
6. Valid Palindrome
7. Palindrome Partitioning
8. Longest Palindromic Substring
9. Longest Common Prefix
10. Find the Index of the First Occurrence in a String
11. Decode String
12. Encode and Decode Strings
13. String to Integer atoi
14. Roman to Integer
15. Integer to Roman
16. Zigzag Conversion
17. Multiply Strings
18. Add Binary
19. Compare Version Numbers
20. Simplify Path
21. Valid Parentheses
22. Generate Parentheses
23. Find All Anagrams in a String
24. Permutation in String
25. Word Break
26. Word Ladder
27. Text Justification
28. Basic Calculator
29. Repeated Substring Pattern
30. Longest Valid Parentheses
31. Reverse Words in a String
32. Reverse String
33. Reverse Vowels of a String
34. Valid Palindrome II
35. Isomorphic Strings
36. Word Pattern
37. Ransom Note
38. First Unique Character in a String
39. Valid Number
40. Count and Say
41. Longest Common Subsequence
42. Edit Distance
43. Regular Expression Matching
44. Wildcard Matching
45. Minimum Window Subsequence
46. Shortest Palindrome
47. Longest Duplicate Substring
48. Substring with Concatenation of All Words
49. Letter Combinations of a Phone Number
50. Restore IP Addresses

## 3. Hash Table - Top 50

Architect focus: O(1) lookup, counting, deduplication, grouping, key design, and collision-aware reasoning.

1. Two Sum
2. Group Anagrams
3. Valid Anagram
4. Longest Substring Without Repeating Characters
5. Top K Frequent Elements
6. Contains Duplicate II
7. Subarray Sum Equals K
8. Isomorphic Strings
9. Word Pattern
10. Longest Consecutive Sequence
11. 4Sum II
12. Minimum Window Substring
13. Copy List with Random Pointer
14. Happy Number
15. Insert Delete GetRandom O(1)
16. First Unique Character in a String
17. Design HashMap
18. LRU Cache
19. Brick Wall
20. Encode and Decode TinyURL
21. Ransom Note
22. Jewels and Stones
23. Intersection of Two Arrays
24. Intersection of Two Arrays II
25. Find Duplicate File in System
26. Logger Rate Limiter
27. Subdomain Visit Count
28. Contiguous Array
29. Valid Sudoku
30. Group Shifted Strings
31. Alien Dictionary
32. Randomized Set
33. Randomized Collection
34. Time Based Key-Value Store
35. Find All Anagrams in a String
36. Permutation in String
37. Longest Harmonious Subsequence
38. Number of Good Pairs
39. Pairs of Songs With Total Durations Divisible by 60
40. Design Underground System
41. Snapshot Array
42. All O(1) Data Structure
43. Max Points on a Line
44. Detect Squares
45. Equal Row and Column Pairs
46. Find Common Characters
47. Unique Number of Occurrences
48. Tuple with Same Product
49. Count Nice Pairs in an Array
50. Analyze User Website Visit Pattern

## 4. Math - Top 50

Architect focus: Arithmetic invariants, modular arithmetic, geometry, combinatorics, and numeric edge cases.

1. Palindrome Number
2. Reverse Integer
3. Pow(x, n)
4. Sqrt(x)
5. Divide Two Integers
6. Plus One
7. Add Binary
8. Multiply Strings
9. Excel Sheet Column Number
10. Happy Number
11. Count Primes
12. Ugly Number
13. Ugly Number II
14. Integer Break
15. Fraction to Recurring Decimal
16. Max Points on a Line
17. Robot Bounded In Circle
18. Angle Between Hands of a Clock
19. Mirror Reflection
20. Minimum Moves to Equal Array Elements II
21. Integer to Roman
22. Roman to Integer
23. Bulb Switcher
24. Perfect Squares
25. Water and Jug Problem
26. Power of Two
27. Power of Three
28. Power of Four
29. Number of 1 Bits
30. Counting Bits
31. Sum of Two Integers
32. Hamming Distance
33. Total Hamming Distance
34. Missing Number
35. Arranging Coins
36. Factorial Trailing Zeroes
37. Excel Sheet Column Title
38. Self Dividing Numbers
39. Valid Perfect Square
40. Nth Magical Number
41. Super Pow
42. Smallest Good Base
43. Reach a Number
44. Poor Pigs
45. Random Point in Non-overlapping Rectangles
46. Random Point in a Circle
47. Rectangle Area
48. Rectangle Overlap
49. Check If It Is a Straight Line
50. K Closest Points to Origin

## 5. Dynamic Programming - Top 50

Architect focus: State definition, recurrence, transitions, memoization, tabulation, and optimization.

1. Climbing Stairs
2. House Robber
3. House Robber II
4. Coin Change
5. Longest Increasing Subsequence
6. Longest Common Subsequence
7. Edit Distance
8. Word Break
9. Decode Ways
10. Unique Paths
11. Unique Paths II
12. Minimum Path Sum
13. Partition Equal Subset Sum
14. Target Sum
15. Combination Sum IV
16. Palindromic Substrings
17. Longest Palindromic Subsequence
18. Maximum Product Subarray
19. Best Time to Buy and Sell Stock with Cooldown
20. Regular Expression Matching
21. Wildcard Matching
22. Burst Balloons
23. Interleaving String
24. Distinct Subsequences
25. Dungeon Game
26. Paint House
27. Paint Fence
28. Perfect Squares
29. 0/1 Knapsack
30. Rod Cutting
31. Triangle
32. Min Cost Climbing Stairs
33. House Robber III
34. Best Time to Buy and Sell Stock III
35. Best Time to Buy and Sell Stock IV
36. Best Time to Buy and Sell Stock with Transaction Fee
37. Longest Valid Parentheses
38. Maximal Square
39. Maximal Rectangle
40. Count Square Submatrices with All Ones
41. Delete and Earn
42. Minimum Falling Path Sum
43. Cherry Pickup
44. Cherry Pickup II
45. Stone Game
46. Stone Game II
47. Stone Game III
48. Predict the Winner
49. Can I Win
50. Scramble String

## 6. Sorting - Top 50

Architect focus: Ordering, custom comparators, intervals, stability, external sorting, and ranking.

1. Merge Intervals
2. Sort Colors
3. Meeting Rooms II
4. Kth Largest Element in an Array
5. Top K Frequent Elements
6. Largest Number
7. Reorder Data in Log Files
8. Sort Characters By Frequency
9. Wiggle Sort II
10. Minimum Number of Arrows to Burst Balloons
11. Non-overlapping Intervals
12. Queue Reconstruction by Height
13. Merge Sorted Array
14. H-Index
15. Maximum Gap
16. Relative Sort Array
17. Sort List
18. Insertion Sort List
19. Car Fleet
20. Rank Teams by Votes
21. Sort an Array
22. Merge Sort
23. Quick Sort
24. Heap Sort
25. Counting Sort
26. Bucket Sort
27. Radix Sort
28. Shell Sort
29. Sort Array by Increasing Frequency
30. Sort the Matrix Diagonally
31. Pancake Sorting
32. Sort Integers by The Number of 1 Bits
33. Custom Sort String
34. K Closest Points to Origin
35. Find K Closest Elements
36. Meeting Rooms
37. Employee Free Time
38. Accounts Merge
39. Group Anagrams
40. Valid Anagram
41. Contains Duplicate
42. Contains Duplicate III
43. Find Right Interval
44. Minimum Meeting Rooms
45. The Skyline Problem
46. External Merge Sort
47. Sort Nearly Sorted Array
48. Sort Transformed Array
49. Sort Jumbled Numbers
50. Sort Vowels in a String

## 7. Greedy - Top 50

Architect focus: Local choice proof, exchange argument, sorting plus choice, and counterexamples.

1. Jump Game
2. Jump Game II
3. Gas Station
4. Task Scheduler
5. Partition Labels
6. Non-overlapping Intervals
7. Minimum Number of Arrows to Burst Balloons
8. Queue Reconstruction by Height
9. Candy
10. Assign Cookies
11. Lemonade Change
12. Boats to Save People
13. Best Time to Buy and Sell Stock II
14. Hand of Straights
15. Reorganize String
16. Dota2 Senate
17. Remove K Digits
18. Monotone Increasing Digits
19. Maximum Swap
20. Meeting Rooms II
21. IPO
22. Course Schedule III
23. Valid Parenthesis String
24. Broken Calculator
25. Minimum Platforms
26. Merge Triplets to Form Target Triplet
27. Maximum Subarray
28. Minimum Deletions to Make Character Frequencies Unique
29. Two City Scheduling
30. Partition Array into Disjoint Intervals
31. Check if a Parentheses String Can Be Valid
32. Minimum Add to Make Parentheses Valid
33. Minimum Number of Refueling Stops
34. Reduce Array Size to The Half
35. Advantage Shuffle
36. Minimum Cost to Hire K Workers
37. Video Stitching
38. Bag of Tokens
39. Score After Flipping Matrix
40. Maximum Units on a Truck
41. Car Pooling
42. Maximum Length of Pair Chain
43. Erase Overlap Intervals
44. Minimum Number of Taps to Open to Water a Garden
45. Split Array into Consecutive Subsequences
46. Rearrange String k Distance Apart
47. Jump Game VI
48. Maximum Performance of a Team
49. Minimum Cost For Tickets
50. Create Maximum Number

## 8. Binary Search - Top 50

Architect focus: Monotonic predicates, rotated arrays, answer-space search, and boundary correctness.

1. Binary Search
2. Search Insert Position
3. Search in Rotated Sorted Array
4. Find Minimum in Rotated Sorted Array
5. Find First and Last Position of Element in Sorted Array
6. Median of Two Sorted Arrays
7. Koko Eating Bananas
8. Capacity To Ship Packages Within D Days
9. Split Array Largest Sum
10. Search a 2D Matrix
11. Search a 2D Matrix II
12. Find Peak Element
13. Time Based Key-Value Store
14. Sqrt(x)
15. Pow(x, n)
16. Guess Number Higher or Lower
17. First Bad Version
18. Find K Closest Elements
19. Kth Smallest Element in a Sorted Matrix
20. Minimum Number of Days to Make m Bouquets
21. Allocate Minimum Pages
22. Aggressive Cows
23. Magnetic Force Between Two Balls
24. Search in Rotated Sorted Array II
25. Peak Index in a Mountain Array
26. Find Minimum in Rotated Sorted Array II
27. Search in a Sorted Array of Unknown Size
28. Find Smallest Letter Greater Than Target
29. Valid Perfect Square
30. Arranging Coins
31. H-Index II
32. Intersection of Two Arrays
33. Single Element in a Sorted Array
34. Find Right Interval
35. Random Pick with Weight
36. Online Election
37. Snapshot Array
38. Find the Duplicate Number
39. Missing Element in Sorted Array
40. Longest Increasing Subsequence
41. Russian Doll Envelopes
42. Maximum Number of Removable Characters
43. Heaters
44. Minimized Maximum of Products Distributed to Any Store
45. Maximum Candies Allocated to K Children
46. Find the Smallest Divisor Given a Threshold
47. Minimum Limit of Balls in a Bag
48. Sell Diminishing-Valued Colored Balls
49. Maximum Running Time of N Computers
50. Nth Magical Number

## 9. Depth-First Search - Top 50

Architect focus: Recursive traversal, state marking, backtracking, cycle detection, and graph/tree exploration.

1. Number of Islands
2. Clone Graph
3. Course Schedule
4. Course Schedule II
5. Pacific Atlantic Water Flow
6. Surrounded Regions
7. Word Search
8. Generate Parentheses
9. Subsets
10. Permutations
11. Combination Sum
12. N-Queens
13. Path Sum
14. Path Sum II
15. Binary Tree Maximum Path Sum
16. Validate Binary Search Tree
17. Lowest Common Ancestor of a Binary Tree
18. Serialize and Deserialize Binary Tree
19. Accounts Merge
20. Evaluate Division
21. Redundant Connection
22. Reconstruct Itinerary
23. Alien Dictionary
24. Critical Connections in a Network
25. Remove Invalid Parentheses
26. Number of Provinces
27. Graph Valid Tree
28. All Paths From Source to Target
29. Find Eventual Safe States
30. Keys and Rooms
31. Flood Fill
32. Max Area of Island
33. Island Perimeter
34. Distinct Islands
35. Closed Island
36. Number of Enclaves
37. Minesweeper
38. The Maze
39. The Maze II
40. The Maze III
41. Employee Importance
42. Nested List Weight Sum
43. Nested List Weight Sum II
44. Flatten Nested List Iterator
45. Binary Tree Paths
46. Sum Root to Leaf Numbers
47. Recover Binary Search Tree
48. House Robber III
49. Delete Nodes And Return Forest
50. Most Stones Removed with Same Row or Column

## 10. Database - Top 50

Architect focus: SQL joins, grouping, ranking, window functions, deduplication, and query correctness.

1. Combine Two Tables
2. Second Highest Salary
3. Nth Highest Salary
4. Rank Scores
5. Consecutive Numbers
6. Employees Earning More Than Their Managers
7. Duplicate Emails
8. Customers Who Never Order
9. Department Highest Salary
10. Department Top Three Salaries
11. Trips and Users
12. Game Play Analysis I
13. Game Play Analysis II
14. Game Play Analysis III
15. Game Play Analysis IV
16. Rising Temperature
17. Exchange Seats
18. Managers with at Least 5 Direct Reports
19. Human Traffic of Stadium
20. Movie Rating
21. Restaurant Growth
22. Product Sales Analysis I
23. Sales Person
24. Tree Node
25. Confirmation Rate
26. Investments in 2016
27. Project Employees I
28. Immediate Food Delivery II
29. Last Person to Fit in the Bus
30. Monthly Transactions I
31. User Activity for the Past 30 Days I
32. User Activity for the Past 30 Days II
33. Market Analysis I
34. Market Analysis II
35. Reported Posts
36. Active Businesses
37. Page Recommendations
38. Students and Examinations
39. Customer Placing the Largest Number of Orders
40. Sales Analysis III
41. Product Price at a Given Date
42. Queries Quality and Percentage
43. Monthly Transactions II
44. Tournament Winners
45. Find Median Given Frequency of Numbers
46. Ads Performance
47. Countries You Can Safely Invest In
48. Group Sold Products By The Date
49. The Number of Employees Which Report to Each Employee
50. Primary Department for Each Employee

## 11. Bit Manipulation - Top 49

Architect focus: XOR, masks, shifts, subsets, parity, integer representation, and overflow.

1. Single Number
2. Single Number II
3. Single Number III
4. Number of 1 Bits
5. Counting Bits
6. Reverse Bits
7. Bitwise AND of Numbers Range
8. Missing Number
9. Sum of Two Integers
10. Power of Two
11. Power of Four
12. Hamming Distance
13. Total Hamming Distance
14. Maximum XOR of Two Numbers in an Array
15. Find the Difference
16. UTF-8 Validation
17. Repeated DNA Sequences
18. Subsets
19. Subsets II
20. Gray Code
21. Divide Two Integers
22. Integer Replacement
23. Complement of Base 10 Integer
24. Minimum Flips to Make a OR b Equal to c
25. Maximum Product of Word Lengths
26. Power of Three
27. Binary Number with Alternating Bits
28. Number Complement
29. Prime Number of Set Bits in Binary Representation
30. Bitwise ORs of Subarrays
31. Find Kth Bit in Nth Binary String
32. Minimum One Bit Operations to Make Integers Zero
33. XOR Queries of a Subarray
34. Decode XORed Array
35. Decode XORed Permutation
36. Count Triplets That Can Form Two Arrays of Equal XOR
37. Maximum XOR With an Element From Array
38. Find the Longest Substring Containing Vowels in Even Counts
39. Minimum Number of Flips to Convert Binary Matrix to Zero Matrix
40. Sort Integers by The Number of 1 Bits
41. Smallest Sufficient Team
42. Shortest Path Visiting All Nodes
43. Can I Win
44. Stickers to Spell Word
45. Beautiful Arrangement
46. Matchsticks to Square
47. Partition to K Equal Sum Subsets
48. Bitmask N-Queens
49. Bitmask Sudoku Solver

## 12. Matrix - Top 50

Architect focus: Grid traversal, coordinate transforms, BFS/DFS, prefix matrices, and in-place marking.

1. Set Matrix Zeroes
2. Spiral Matrix
3. Rotate Image
4. Search a 2D Matrix
5. Search a 2D Matrix II
6. Word Search
7. Number of Islands
8. Maximal Square
9. Maximal Rectangle
10. Game of Life
11. Pacific Atlantic Water Flow
12. Surrounded Regions
13. Rotting Oranges
14. Shortest Path in Binary Matrix
15. Unique Paths
16. Minimum Path Sum
17. Toeplitz Matrix
18. Diagonal Traverse
19. Kth Smallest Element in a Sorted Matrix
20. Valid Sudoku
21. Sudoku Solver
22. Island Perimeter
23. Flood Fill
24. Walls and Gates
25. 01 Matrix
26. Number of Enclaves
27. Closed Island
28. Max Area of Island
29. Count Submatrices With All Ones
30. Matrix Block Sum
31. Range Sum Query 2D - Immutable
32. Range Sum Query 2D - Mutable
33. The Maze
34. The Maze II
35. The Maze III
36. Shortest Bridge
37. Making A Large Island
38. Swim in Rising Water
39. Path With Minimum Effort
40. Minimum Cost to Make at Least One Valid Path in a Grid
41. Where Will the Ball Fall
42. Robot Room Cleaner
43. Battleships in a Board
44. Count Servers that Communicate
45. Number of Distinct Islands
46. Minimum Falling Path Sum
47. Cherry Pickup
48. Cherry Pickup II
49. Longest Increasing Path in a Matrix
50. Largest Plus Sign

## 13. Tree - Top 50

Architect focus: Recursive structure, traversal, LCA, serialization, balanced trees, and subtree invariants.

1. Maximum Depth of Binary Tree
2. Same Tree
3. Invert Binary Tree
4. Binary Tree Level Order Traversal
5. Validate Binary Search Tree
6. Lowest Common Ancestor of a Binary Tree
7. Serialize and Deserialize Binary Tree
8. Subtree of Another Tree
9. Construct Binary Tree from Preorder and Inorder Traversal
10. Binary Tree Maximum Path Sum
11. Diameter of Binary Tree
12. Balanced Binary Tree
13. Path Sum
14. Path Sum II
15. Kth Smallest Element in a BST
16. Binary Search Tree Iterator
17. N-ary Tree Level Order Traversal
18. Convert Sorted Array to BST
19. Flatten Binary Tree to Linked List
20. Populating Next Right Pointers
21. Recover Binary Search Tree
22. Delete Node in a BST
23. Count Complete Tree Nodes
24. House Robber III
25. Symmetric Tree
26. Binary Tree Right Side View
27. Binary Tree Zigzag Level Order Traversal
28. Vertical Order Traversal of a Binary Tree
29. Boundary of Binary Tree
30. Find Duplicate Subtrees
31. Lowest Common Ancestor of a Binary Search Tree
32. Insert into a Binary Search Tree
33. Trim a Binary Search Tree
34. Range Sum of BST
35. Two Sum IV - Input is a BST
36. Convert Sorted List to Binary Search Tree
37. Serialize and Deserialize BST
38. All Nodes Distance K in Binary Tree
39. Binary Tree Cameras
40. Delete Nodes And Return Forest
41. Path Sum III
42. Sum Root to Leaf Numbers
43. Binary Tree Paths
44. Recover a Tree From Preorder Traversal
45. Construct Binary Search Tree from Preorder Traversal
46. Find Mode in Binary Search Tree
47. Minimum Absolute Difference in BST
48. Closest Binary Search Tree Value
49. Closest Binary Search Tree Value II
50. Balance a Binary Search Tree

## 14. Breadth-First Search - Top 49

Architect focus: Shortest unweighted paths, levels, multi-source expansion, and queue discipline.

1. Binary Tree Level Order Traversal
2. Rotting Oranges
3. Word Ladder
4. Open the Lock
5. Shortest Path in Binary Matrix
6. Walls and Gates
7. Number of Islands
8. Clone Graph
9. Course Schedule
10. Minimum Genetic Mutation
11. Bus Routes
12. Snakes and Ladders
13. Pacific Atlantic Water Flow
14. 01 Matrix
15. Perfect Squares
16. Jump Game III
17. Shortest Bridge
18. As Far from Land as Possible
19. Minimum Knight Moves
20. Cut Off Trees for Golf Event
21. Evaluate Division
22. Alien Dictionary
23. Is Graph Bipartite
24. Multi-source Infection Spread
25. Word Ladder II
26. Sliding Puzzle
27. Shortest Path Visiting All Nodes
28. Shortest Path to Get All Keys
29. Race Car
30. The Maze
31. The Maze II
32. The Maze III
33. Employee Importance
34. Nested List Weight Sum
35. Find Largest Value in Each Tree Row
36. Average of Levels in Binary Tree
37. Minimum Depth of Binary Tree
38. Populating Next Right Pointers in Each Node
39. Binary Tree Right Side View
40. All Nodes Distance K in Binary Tree
41. Number of Connected Components in an Undirected Graph
42. Graph Valid Tree
43. Possible Bipartition
44. Keys and Rooms
45. Nearest Exit from Entrance in Maze
46. Minimum Height Trees
47. Open Lock Bidirectional BFS
48. Remove Invalid Parentheses
49. Pacific Atlantic Multi-source BFS

## 15. Two Pointers - Top 50

Architect focus: Sorted scans, partitioning, palindromes, fast/slow pointers, and in-place movement.

1. Valid Palindrome
2. Two Sum II - Input Array Is Sorted
3. 3Sum
4. Container With Most Water
5. Trapping Rain Water
6. Remove Duplicates from Sorted Array
7. Move Zeroes
8. Sort Colors
9. Boats to Save People
10. 3Sum Closest
11. Backspace String Compare
12. Squares of a Sorted Array
13. 4Sum
14. Remove Nth Node From End of List
15. Linked List Cycle
16. Palindrome Linked List
17. Merge Sorted Array
18. Intersection of Two Arrays II
19. Longest Mountain in Array
20. Partition Labels
21. Dutch National Flag
22. Minimum Window Subsequence
23. Reverse Vowels of a String
24. Valid Palindrome II
25. Linked List Cycle II
26. Remove Duplicates from Sorted Array II
27. Remove Element
28. Middle of the Linked List
29. Intersection of Two Linked Lists
30. Reorder List
31. Rotate List
32. Reverse Linked List II
33. Sort List
34. Merge Two Sorted Lists
35. Merge k Sorted Lists
36. Find the Duplicate Number
37. Happy Number
38. Circular Array Loop
39. Subarray Product Less Than K
40. Minimum Size Subarray Sum
41. Longest Substring Without Repeating Characters
42. Minimum Window Substring
43. Permutation in String
44. Find All Anagrams in a String
45. Push Dominoes
46. Interval List Intersections
47. Next Permutation
48. Compare Version Numbers
49. Container With Most Water Follow-up
50. 3Sum Smaller

## 16. Prefix Sum - Top 50

Architect focus: Cumulative state, range queries, subarray counts, difference arrays, and 2D sums.

1. Range Sum Query - Immutable
2. Range Sum Query 2D - Immutable
3. Subarray Sum Equals K
4. Continuous Subarray Sum
5. Product of Array Except Self
6. Find Pivot Index
7. Minimum Size Subarray Sum
8. Maximum Size Subarray Sum Equals k
9. Corporate Flight Bookings
10. Car Pooling
11. Number of Sub-arrays with Odd Sum
12. Count Number of Nice Subarrays
13. Subarrays Divisible by K
14. Maximum Sum Circular Subarray
15. Contiguous Array
16. Path Sum III
17. Binary Subarrays With Sum
18. Matrix Block Sum
19. Range Addition
20. Meeting Rooms via Difference Array
21. Split Array Largest Sum
22. Largest Altitude
23. Zero Sum Subarray
24. 2D Difference Matrix
25. Prefix XOR Range Query
26. Count of Range Sum
27. Range Sum Query - Mutable
28. Range Sum Query 2D - Mutable
29. Find the Highest Altitude
30. Running Sum of 1d Array
31. Maximum Average Subarray I
32. Maximum Average Subarray II
33. Minimum Operations to Reduce X to Zero
34. Ways to Split Array Into Three Subarrays
35. Number of Ways to Split Array
36. Count Vowel Strings in Ranges
37. Plates Between Candles
38. Minimum Value to Get Positive Step by Step Sum
39. Shifting Letters
40. Shifting Letters II
41. Difference Array Range Updates
42. Flight Bookings Difference Array
43. My Calendar III Difference Map
44. Subarray Sums Divisible by K
45. Make Sum Divisible by P
46. Longest Well-Performing Interval
47. Sum of Absolute Differences in a Sorted Array
48. Minimum Penalty for a Shop
49. Maximum Score After Splitting a String
50. Find Good Days to Rob the Bank

## 17. Heap (Priority Queue) - Top 50

Architect focus: Top-K, streaming order, scheduling, k-way merge, and priority updates.

1. Kth Largest Element in an Array
2. Top K Frequent Elements
3. Find Median from Data Stream
4. Merge k Sorted Lists
5. Task Scheduler
6. K Closest Points to Origin
7. Reorganize String
8. Sort Characters By Frequency
9. Kth Smallest Element in a Sorted Matrix
10. Last Stone Weight
11. Ugly Number II
12. Meeting Rooms II
13. Smallest Range Covering Elements from K Lists
14. IPO
15. Sliding Window Median
16. Design Twitter
17. Super Ugly Number
18. Employee Free Time
19. Minimum Cost to Connect Sticks
20. Process Tasks Using Servers
21. Single-Threaded CPU
22. Maximum Performance of a Team
23. The Skyline Problem
24. Find K Pairs with Smallest Sums
25. Dijkstra Shortest Path
26. Network Delay Time
27. Path With Minimum Effort
28. Swim in Rising Water
29. Cheapest Flights Within K Stops
30. Trapping Rain Water II
31. Kth Largest Element in a Stream
32. Seat Reservation Manager
33. Stock Price Fluctuation
34. Total Cost to Hire K Workers
35. Maximum Subsequence Score
36. Minimum Number of Refueling Stops
37. Rearrange String k Distance Apart
38. Minimum Cost to Hire K Workers
39. Find Right Interval
40. Course Schedule III
41. Kth Smallest Prime Fraction
42. Furthest Building You Can Reach
43. Maximum Average Pass Ratio
44. Reduce Array Size to The Half
45. Meeting Rooms III
46. Minimum Interval to Include Each Query
47. K Closest Points Stream
48. Merge K Sorted Arrays
49. Top K Frequent Words
50. Sort Characters by Frequency

## 18. Simulation - Top 50

Architect focus: State machines, event processing, rules implementation, and correctness by invariants.

1. Game of Life
2. Spiral Matrix
3. Robot Bounded In Circle
4. Walking Robot Simulation
5. Zigzag Conversion
6. Text Justification
7. Basic Calculator II
8. Asteroid Collision
9. Design Parking System
10. Number of Recent Calls
11. Dota2 Senate
12. Robot Return to Origin
13. Prison Cells After N Days
14. Champagne Tower
15. Where Will the Ball Fall
16. Minimum Domino Rotations For Equal Row
17. Validate Stack Sequences
18. Design Underground System
19. LRU Cache Operation Trace
20. Tic-Tac-Toe Winner
21. Snake Game
22. Circular Game Losers
23. Excel Sheet Column Conversion
24. Browser History Simulation
25. Task Scheduler Simulation
26. Baseball Game
27. Crawler Log Folder
28. Design Browser History
29. Design Snake Game
30. Design Hit Counter
31. Design Circular Queue
32. Design Circular Deque
33. Robot Room Cleaner
34. The Robot Bounded in Circle Follow-up
35. Watering Plants
36. Walking Robot Simulation II
37. Find the Winner of the Circular Game
38. Number of Students Unable to Eat Lunch
39. Reveal Cards In Increasing Order
40. Push Dominoes
41. Time Needed to Buy Tickets
42. Design Front Middle Back Queue
43. Implement Stack using Queues
44. Implement Queue using Stacks
45. Moving Average from Data Stream
46. Hit Counter
47. Logger Rate Limiter
48. My Calendar I
49. My Calendar II
50. My Calendar III

## 19. Counting - Top 50

Architect focus: Frequency arrays, histograms, buckets, bounded domains, and count-based optimization.

1. Top K Frequent Elements
2. Sort Characters By Frequency
3. Valid Anagram
4. Group Anagrams
5. First Unique Character in a String
6. Ransom Note
7. Majority Element
8. Majority Element II
9. Contains Duplicate
10. Intersection of Two Arrays II
11. Find All Anagrams in a String
12. Subdomain Visit Count
13. Number of Good Pairs
14. Jewels and Stones
15. Max Number of K-Sum Pairs
16. Frequency of the Most Frequent Element
17. Count Primes
18. Counting Bits
19. H-Index
20. Bucket-Based Top K
21. Counting Sort Stable Placement
22. Count of Smaller Numbers After Self
23. Count Servers that Communicate
24. Count Number of Nice Subarrays
25. Equal Row and Column Pairs
26. Unique Number of Occurrences
27. Find Common Characters
28. Relative Sort Array
29. Sort Array by Increasing Frequency
30. Sort Characters by Frequency
31. Count Vowels Permutation
32. Count Sorted Vowel Strings
33. Count Binary Substrings
34. Count and Say
35. Count Complete Tree Nodes
36. Number of Matching Subsequences
37. Number of Subarrays with Bounded Maximum
38. Count Square Submatrices with All Ones
39. Subarrays with K Different Integers
40. Number of Boomerangs
41. Tuple with Same Product
42. Count Good Meals
43. Count Nice Pairs in an Array
44. Count Pairs with XOR in a Range
45. Pairs of Songs With Total Durations Divisible by 60
46. Four Sum II
47. Find Duplicate File in System
48. Analyze User Website Visit Pattern
49. Least Number of Unique Integers after K Removals
50. Maximum Number of Balloons

## 20. Graph Theory - Top 50

Architect focus: Graph modeling, traversal, connectivity, cycles, paths, and representation trade-offs.

1. Clone Graph
2. Course Schedule
3. Course Schedule II
4. Number of Islands
5. Pacific Atlantic Water Flow
6. Alien Dictionary
7. Evaluate Division
8. Reconstruct Itinerary
9. Redundant Connection
10. Accounts Merge
11. Network Delay Time
12. Cheapest Flights Within K Stops
13. Min Cost to Connect All Points
14. Critical Connections in a Network
15. Find Eventual Safe States
16. Is Graph Bipartite
17. Word Ladder
18. Bus Routes
19. Shortest Path Visiting All Nodes
20. Number of Connected Components in an Undirected Graph
21. Graph Valid Tree
22. Minimum Height Trees
23. Possible Bipartition
24. Path With Minimum Effort
25. All Paths From Source to Target
26. Keys and Rooms
27. Number of Provinces
28. Redundant Connection II
29. Most Stones Removed with Same Row or Column
30. Regions Cut By Slashes
31. Satisfiability of Equality Equations
32. Swim in Rising Water
33. Bricks Falling When Hit
34. Find the Town Judge
35. Maximal Network Rank
36. Reorder Routes to Make All Paths Lead to the City Zero
37. Minimum Number of Vertices to Reach All Nodes
38. Make Network Connected
39. Detonate the Maximum Bombs
40. Longest Cycle in a Graph
41. Shortest Cycle in a Graph
42. Find if Path Exists in Graph
43. Find Critical and Pseudo-Critical Edges in MST
44. Parallel Courses
45. Parallel Courses II
46. Build Matrix With Conditions
47. Loud and Rich
48. Find All People With Secret
49. Minimum Score of a Path Between Two Cities
50. Modify Graph Edge Weights

## 21. Binary Tree - Top 50

Architect focus: Traversal, recursion, path state, subtree aggregation, and structural transformations.

1. Maximum Depth of Binary Tree
2. Same Tree
3. Invert Binary Tree
4. Binary Tree Level Order Traversal
5. Binary Tree Right Side View
6. Diameter of Binary Tree
7. Balanced Binary Tree
8. Binary Tree Maximum Path Sum
9. Path Sum
10. Path Sum II
11. Path Sum III
12. Lowest Common Ancestor of a Binary Tree
13. Serialize and Deserialize Binary Tree
14. Construct Binary Tree from Preorder and Inorder Traversal
15. Construct Binary Tree from Inorder and Postorder Traversal
16. Flatten Binary Tree to Linked List
17. Populating Next Right Pointers
18. Count Complete Tree Nodes
19. Symmetric Tree
20. Binary Tree Zigzag Level Order Traversal
21. Vertical Order Traversal of a Binary Tree
22. Boundary of Binary Tree
23. House Robber III
24. Delete Leaves With a Given Value
25. Find Duplicate Subtrees
26. Subtree of Another Tree
27. Sum Root to Leaf Numbers
28. Binary Tree Paths
29. Minimum Depth of Binary Tree
30. Average of Levels in Binary Tree
31. Find Largest Value in Each Tree Row
32. All Nodes Distance K in Binary Tree
33. Binary Tree Cameras
34. Delete Nodes And Return Forest
35. Recover a Tree From Preorder Traversal
36. Binary Tree Tilt
37. Maximum Width of Binary Tree
38. Binary Tree Pruning
39. Construct String from Binary Tree
40. Check Completeness of a Binary Tree
41. Cousins in Binary Tree
42. Lowest Common Ancestor of Deepest Leaves
43. Smallest Subtree with all the Deepest Nodes
44. Maximum Difference Between Node and Ancestor
45. Pseudo-Palindromic Paths in a Binary Tree
46. Even Odd Tree
47. Amount of Time for Binary Tree to Be Infected
48. Step-By-Step Directions From a Binary Tree Node to Another
49. Find Leaves of Binary Tree
50. Convert Binary Search Tree to Sorted Doubly Linked List

## 22. Stack - Top 50

Architect focus: Nested state, expression parsing, monotonic patterns, undo semantics, and validation.

1. Valid Parentheses
2. Min Stack
3. Evaluate Reverse Polish Notation
4. Daily Temperatures
5. Car Fleet
6. Largest Rectangle in Histogram
7. Generate Parentheses
8. Asteroid Collision
9. Basic Calculator
10. Basic Calculator II
11. Decode String
12. Remove All Adjacent Duplicates in String II
13. Trapping Rain Water
14. Next Greater Element I
15. Next Greater Element II
16. Online Stock Span
17. Simplify Path
18. Remove K Digits
19. Maximal Rectangle
20. Longest Valid Parentheses
21. Validate Stack Sequences
22. Exclusive Time of Functions
23. 132 Pattern
24. Score of Parentheses
25. Remove Invalid Parentheses
26. Basic Calculator III
27. Baseball Game
28. Crawler Log Folder
29. Implement Queue using Stacks
30. Implement Stack using Queues
31. Design Browser History
32. Flatten Nested List Iterator
33. Binary Search Tree Iterator
34. Peeking Iterator
35. Parsing A Boolean Expression
36. Number of Atoms
37. Minimum Remove to Make Valid Parentheses
38. Check If Word Is Valid After Substitutions
39. Build an Array With Stack Operations
40. Final Prices With a Special Discount in a Shop
41. Minimum Add to Make Parentheses Valid
42. Maximum Nesting Depth of the Parentheses
43. Remove Outermost Parentheses
44. Make The String Great
45. Backspace String Compare
46. Decode At Index
47. Tag Validator
48. Ternary Expression Parser
49. Stack Using Linked List
50. Queue Reconstruction With Stack

## 23. Sliding Window - Top 50

Architect focus: Contiguous window invariants, frequency maps, two-boundary movement, and amortized O(n).

1. Best Time to Buy and Sell Stock
2. Longest Substring Without Repeating Characters
3. Longest Repeating Character Replacement
4. Permutation in String
5. Minimum Window Substring
6. Sliding Window Maximum
7. Minimum Size Subarray Sum
8. Fruit Into Baskets
9. Subarrays with K Different Integers
10. Maximum Number of Vowels in a Substring
11. Get Equal Substrings Within Budget
12. Max Consecutive Ones III
13. Grumpy Bookstore Owner
14. Find All Anagrams in a String
15. Substring with Concatenation of All Words
16. Minimum Operations to Reduce X to Zero
17. Count Number of Nice Subarrays
18. Longest Subarray of 1s After Deleting One Element
19. Maximum Points You Can Obtain from Cards
20. Frequency of the Most Frequent Element
21. Longest Continuous Subarray With Absolute Diff Less Than or Equal Limit
22. Contains Duplicate III
23. Minimum Window Subsequence
24. Sliding Window Median
25. Binary Subarrays With Sum
26. Subarray Product Less Than K
27. Maximum Average Subarray I
28. Maximum Average Subarray II
29. Repeated DNA Sequences
30. Longest Harmonious Subsequence
31. Maximum Erasure Value
32. Number of Substrings Containing All Three Characters
33. Replace the Substring for Balanced String
34. Minimum Size Subarray in Infinite Array
35. Count Subarrays Where Max Element Appears at Least K Times
36. Take K of Each Character From Left and Right
37. Shortest Subarray with Sum at Least K
38. Longest Nice Subarray
39. Minimum Recolors to Get K Consecutive Black Blocks
40. Find K-Length Substrings With No Repeated Characters
41. Find All Good Strings Window Variant
42. Longest Repeating Character Replacement Follow-up
43. Longest Substring with At Most K Distinct Characters
44. Longest Substring with At Most Two Distinct Characters
45. Find the Longest Semi-Repetitive Substring
46. Number of Subarrays of Size K and Average Greater Than Threshold
47. Max Consecutive Ones
48. Max Consecutive Ones II
49. Distinct Numbers in Each Subarray
50. Diet Plan Performance

## 24. Enumeration - Top 50

Architect focus: Systematic case generation, pruning, bitmask enumeration, and complexity control.

1. Subsets
2. Subsets II
3. Permutations
4. Permutations II
5. Combinations
6. Combination Sum
7. Combination Sum II
8. Letter Combinations of a Phone Number
9. Generate Parentheses
10. N-Queens
11. Palindrome Partitioning
12. Expression Add Operators
13. Beautiful Arrangement
14. Restore IP Addresses
15. Gray Code
16. Find All Anagrams in a String
17. 4Sum
18. 3Sum
19. Combination Sum III
20. Maximum Length of a Concatenated String with Unique Characters
21. 24 Game
22. Additive Number
23. Ambiguous Coordinates
24. Sequential Digits
25. Iterator for Combination
26. Brace Expansion
27. Brace Expansion II
28. Letter Case Permutation
29. Generalized Abbreviation
30. Binary Watch
31. Number of Squareful Arrays
32. Closest Subsequence Sum
33. Split Array With Same Average
34. Fair Distribution of Cookies
35. Matchsticks to Square
36. Partition to K Equal Sum Subsets
37. Word Squares
38. Sudoku Solver
39. Word Search
40. Word Search II
41. Remove Invalid Parentheses
42. Different Ways to Add Parentheses
43. Strobogrammatic Number II
44. Strobogrammatic Number III
45. All Possible Full Binary Trees
46. Generate Binary Strings Without Adjacent Zeros
47. Count Number of Maximum Bitwise-OR Subsets
48. The K-th Lexicographical Happy String
49. Lexicographical Numbers
50. Find Kth Lexicographical Number

## 25. Design - Top 48

Architect focus: API contracts, state ownership, complexity guarantees, cache/data-structure composition, and edge cases.

1. LRU Cache
2. LFU Cache
3. Min Stack
4. Design HashMap
5. Design HashSet
6. Insert Delete GetRandom O(1)
7. Design Twitter
8. Find Median from Data Stream
9. Time Based Key-Value Store
10. Design Add and Search Words Data Structure
11. Implement Trie
12. Serialize and Deserialize Binary Tree
13. Design Hit Counter
14. Design Underground System
15. Design Browser History
16. Design Circular Queue
17. Design Circular Deque
18. Peeking Iterator
19. Flatten Nested List Iterator
20. Snapshot Array
21. All O(1) Data Structure
22. Design Search Autocomplete System
23. Design File System
24. Design In-Memory File System
25. Design Snake Game
26. Design Parking System
27. Logger Rate Limiter
28. Moving Average from Data Stream
29. Stock Price Fluctuation
30. Range Module
31. My Calendar I
32. My Calendar II
33. My Calendar III
34. Design Excel Sum Formula
35. Design Tic-Tac-Toe
36. Design Phone Directory
37. Design Compressed String Iterator
38. Design Front Middle Back Queue
39. Design Most Recently Used Queue
40. Design Authentication Manager
41. Design Memory Allocator
42. Design Bitset
43. Design Skiplist
44. Design A Leaderboard
45. Design Bounded Blocking Queue
46. Design Video Sharing Platform
47. Design Food Rating System
48. Design Task Manager

## 26. Backtracking - Top 50

Architect focus: Search tree, choices, constraints, pruning, duplicates, and restoration of state.

1. Subsets
2. Subsets II
3. Permutations
4. Permutations II
5. Combinations
6. Combination Sum
7. Combination Sum II
8. Combination Sum III
9. Letter Combinations of a Phone Number
10. Generate Parentheses
11. N-Queens
12. N-Queens II
13. Sudoku Solver
14. Word Search
15. Palindrome Partitioning
16. Restore IP Addresses
17. Expression Add Operators
18. Beautiful Arrangement
19. Matchsticks to Square
20. Partition to K Equal Sum Subsets
21. Remove Invalid Parentheses
22. Word Search II
23. Maximum Length of a Concatenated String with Unique Characters
24. Unique Paths III
25. The K-th Lexicographical Happy String
26. 24 Game
27. Additive Number
28. Word Squares
29. Strobogrammatic Number II
30. Generalized Abbreviation
31. Letter Case Permutation
32. Brace Expansion
33. Brace Expansion II
34. Split a String Into the Max Number of Unique Substrings
35. Minimum Incompatibility
36. Fair Distribution of Cookies
37. Beautiful Arrangement II
38. Android Unlock Patterns
39. Factor Combinations
40. Combination Iterator
41. Construct the Lexicographically Largest Valid Sequence
42. Find Unique Binary String
43. Count Number of Maximum Bitwise-OR Subsets
44. The Number of Beautiful Subsets
45. Shopping Offers
46. Optimal Account Balancing
47. Cracking the Safe
48. Verbal Arithmetic Puzzle
49. Pyramid Transition Matrix
50. Zuma Game

## 27. Union-Find - Top 50

Architect focus: Connectivity, path compression, union by rank, dynamic components, and cycle detection.

1. Number of Connected Components in an Undirected Graph
2. Graph Valid Tree
3. Redundant Connection
4. Redundant Connection II
5. Accounts Merge
6. Number of Islands
7. Number of Islands II
8. Most Stones Removed with Same Row or Column
9. Satisfiability of Equality Equations
10. Min Cost to Connect All Points
11. Couples Holding Hands
12. Regions Cut By Slashes
13. Similar String Groups
14. Path With Minimum Effort
15. Swim in Rising Water
16. Bricks Falling When Hit
17. Evaluate Division
18. Number of Provinces
19. Lexicographically Smallest Equivalent String
20. Checking Existence of Edge Length Limited Paths
21. Making A Large Island
22. Sentence Similarity II
23. Friend Circles
24. Find if Path Exists in Graph
25. Remove Max Number of Edges to Keep Graph Fully Traversable
26. Find Critical and Pseudo-Critical Edges in Minimum Spanning Tree
27. Greatest Common Divisor Traversal
28. Minimum Hamming Distance After Swap Operations
29. Process Restricted Friend Requests
30. Number of Good Paths
31. Rank Transform of a Matrix
32. Largest Component Size by Common Factor
33. Smallest String With Swaps
34. Find All People With Secret
35. Accounts Merge Follow-up
36. Dynamic Connectivity
37. Union-Find with Rollback
38. Offline Connectivity Queries
39. Percolation
40. Kruskal Minimum Spanning Tree
41. Minimum Cost to Connect All Points
42. Optimize Water Distribution in a Village
43. Connecting Cities With Minimum Cost
44. Last Day Where You Can Still Cross
45. Path Existence Queries in a Graph I
46. Path Existence Queries in a Graph II
47. Malware Spread
48. Minimize Malware Spread
49. Minimize Malware Spread II
50. Graph Connectivity With Threshold

## 28. Number Theory - Top 50

Architect focus: GCD/LCM, primes, modular arithmetic, divisibility, and integer constraints.

1. Count Primes
2. Ugly Number
3. Ugly Number II
4. Super Ugly Number
5. Happy Number
6. Power of Two
7. Power of Three
8. Power of Four
9. Sqrt(x)
10. Pow(x, n)
11. Greatest Common Divisor of Strings
12. Water and Jug Problem
13. Fraction to Recurring Decimal
14. Perfect Squares
15. Integer Replacement
16. Nth Magical Number
17. Prime Palindrome
18. Smallest Good Base
19. Bulb Switcher
20. Mirror Reflection
21. Count Good Numbers
22. Modular Exponentiation
23. Extended GCD
24. Chinese Remainder Theorem
25. Euler Totient
26. Palindrome Number
27. Reverse Integer
28. Divide Two Integers
29. Plus One
30. Add Binary
31. Multiply Strings
32. Excel Sheet Column Number
33. Integer Break
34. Max Points on a Line
35. Robot Bounded In Circle
36. Angle Between Hands of a Clock
37. Minimum Moves to Equal Array Elements II
38. Integer to Roman
39. Roman to Integer
40. Self Dividing Numbers
41. Arranging Coins
42. Factorial Trailing Zeroes
43. Valid Perfect Square
44. Super Pow
45. Powerful Integers
46. Sum of Square Numbers
47. Consecutive Numbers Sum
48. Count Ways to Make Array With Product
49. Find Greatest Common Divisor of Array
50. Minimum Deletions to Make Array Divisible

## 29. Linked List - Top 50

Architect focus: Pointer mutation, sentinel nodes, cycle detection, reversal, and memory-safe updates.

1. Reverse Linked List
2. Merge Two Sorted Lists
3. Linked List Cycle
4. Linked List Cycle II
5. Remove Nth Node From End of List
6. Reorder List
7. Add Two Numbers
8. Copy List with Random Pointer
9. Merge k Sorted Lists
10. Palindrome Linked List
11. Intersection of Two Linked Lists
12. Sort List
13. Insertion Sort List
14. Rotate List
15. Swap Nodes in Pairs
16. Reverse Nodes in k-Group
17. Remove Duplicates from Sorted List
18. Remove Duplicates from Sorted List II
19. Partition List
20. Flatten a Multilevel Doubly Linked List
21. LRU Cache
22. Design Linked List
23. Odd Even Linked List
24. Delete Node in a Linked List
25. Middle of the Linked List
26. Reverse Linked List II
27. Add Two Numbers II
28. Split Linked List in Parts
29. Linked List Components
30. Next Greater Node In Linked List
31. Remove Linked List Elements
32. Convert Binary Number in a Linked List to Integer
33. Design Browser History
34. Design Circular Deque
35. Design Circular Queue
36. All O(1) Data Structure
37. LFU Cache
38. Insert into a Sorted Circular Linked List
39. Flatten Binary Tree to Linked List
40. Convert Sorted List to Binary Search Tree
41. Remove Zero Sum Consecutive Nodes from Linked List
42. Swapping Nodes in a Linked List
43. Merge In Between Linked Lists
44. Delete the Middle Node of a Linked List
45. Maximum Twin Sum of a Linked List
46. Double a Number Represented as a Linked List
47. Reverse Nodes in Even Length Groups
48. Linked List Random Node
49. Browser History with Doubly Linked List
50. Deque with Doubly Linked List

## 30. Segment Tree - Top 50

Architect focus: Range queries, range updates, lazy propagation, and merge functions.

1. Range Sum Query - Mutable
2. Range Minimum Query
3. Range Maximum Query
4. Count of Smaller Numbers After Self
5. Reverse Pairs
6. The Skyline Problem
7. My Calendar I
8. My Calendar II
9. My Calendar III
10. Falling Squares
11. Range Module
12. Longest Increasing Subsequence II
13. Booking Calendar with Lazy Propagation
14. Interval Add Range Sum
15. Interval Assign Range Minimum
16. Maximum Segment Sum After Removals
17. Dynamic Segment Tree for Sparse Coordinates
18. 2D Segment Tree Range Query
19. Segment Tree Beats
20. Coordinate-Compressed Segment Tree
21. Create Sorted Array through Instructions
22. Count of Range Sum
23. Rectangle Area II
24. Handling Sum Queries After Update
25. Peaks in Array
26. Maximum Sum Queries
27. Minimum Interval to Include Each Query
28. Online Majority Element in Subarray
29. Block Placement Queries
30. Range Frequency Queries
31. Longest Subarray with Absolute Diff Limit via Segment Tree
32. K-th Order Statistic Segment Tree
33. Lazy Propagation Range Add Range Max
34. Lazy Propagation Range Assign Range Sum
35. Segment Tree for GCD Range Query
36. Segment Tree for LCM Range Query
37. Segment Tree for XOR Range Query
38. Segment Tree for Maximum Subarray Sum
39. Segment Tree for First Greater Element
40. Segment Tree for Hotel Queries
41. Segment Tree for Nested Intervals Count
42. Segment Tree for Sweep Line Area
43. Segment Tree for Skyline
44. Segment Tree for Calendar Overlaps
45. Segment Tree for Inversion Count
46. Segment Tree for Dynamic LIS
47. Segment Tree for Range Chmax
48. Segment Tree for Range Chmin
49. Persistent Segment Tree K-th Number
50. Merge Sort Tree Range Query

## 31. Ordered Set - Top 50

Architect focus: Balanced BST operations, floor/ceiling, rank, interval queries, and sliding order statistics.

1. Contains Duplicate III
2. My Calendar I
3. My Calendar II
4. Range Module
5. Data Stream as Disjoint Intervals
6. Count of Smaller Numbers After Self
7. Reverse Pairs
8. The Skyline Problem
9. Sliding Window Median
10. Longest Continuous Subarray With Absolute Diff Less Than or Equal Limit
11. K Empty Slots
12. Exam Room
13. Hand of Straights
14. Find Right Interval
15. Summary Ranges
16. Calendar Double Booking
17. Closest Room
18. Online Rank Query
19. Floor and Ceiling in Stream
20. Active Interval Sweep Set
21. My Calendar III
22. Range Frequency Queries
23. Minimum Absolute Difference Queries
24. Number of Flowers in Full Bloom
25. Maximum Sum Queries
26. Minimum Interval to Include Each Query
27. Count Intervals
28. Food Ratings System
29. Seat Reservation Manager
30. Snapshot Array
31. Time Based Key-Value Store
32. Stock Price Fluctuation
33. Design a Leaderboard
34. All O(1) Data Structure
35. LFU Cache
36. Range Module with TreeMap
37. Merge Intervals with Ordered Set
38. Insert Interval with Ordered Set
39. Longest Subarray with Limit using TreeMap
40. Sliding Window Median with Two Heaps and Ordered Set
41. Rank Transform of a Stream
42. Median Finder with Ordered Multiset
43. Find K Closest Elements
44. Find K-th Smallest Pair Distance
45. Smallest Range Covering Elements from K Lists
46. Maximum Number of Events That Can Be Attended
47. Employee Free Time
48. Meeting Scheduler
49. Amount of New Area Painted Each Day
50. Avoid Flood in The City

## 32. Monotonic Stack - Top 50

Architect focus: Next greater/smaller, histogram areas, span, contribution counting, and amortized proof.

1. Daily Temperatures
2. Next Greater Element I
3. Next Greater Element II
4. Largest Rectangle in Histogram
5. Maximal Rectangle
6. Online Stock Span
7. Trapping Rain Water
8. Remove K Digits
9. 132 Pattern
10. Sum of Subarray Minimums
11. Final Prices With a Special Discount in a Shop
12. Car Fleet
13. Asteroid Collision
14. Number of Visible People in a Queue
15. Maximum Width Ramp
16. Beautiful Towers I
17. Beautiful Towers II
18. Steps to Make Array Non-decreasing
19. Next Greater Node In Linked List
20. Find the Most Competitive Subsequence
21. Remove Duplicate Letters
22. Smallest Subsequence of Distinct Characters
23. Shortest Unsorted Continuous Subarray
24. Create Maximum Number
25. Lexicographically Smallest Subsequence After Removing K Digits
26. Minimum Cost Tree From Leaf Values
27. Maximum Subarray Min-Product
28. Count Submatrices With All Ones
29. Total Strength of Wizards
30. Robot Collisions
31. Validate Stack Sequences
32. Buildings With an Ocean View
33. Largest Rectangle in Binary Matrix
34. Previous Smaller Element
35. Next Smaller Element
36. Stock Span Problem
37. Nearest Smaller to Left
38. Nearest Greater to Left
39. Nearest Greater to Right
40. Nearest Smaller to Right
41. Histogram Max Area with Sentinels
42. Sliding Window Maximum with Monotonic Deque
43. Maximum of Minimum for Every Window Size
44. Remove Nodes From Linked List
45. Find Building Where Alice and Bob Can Meet
46. Sum of Subarray Ranges
47. Minimum Number of People to Teach
48. Monotonic Stack for Visibility
49. Monotonic Stack for Contribution Counting
50. Monotonic Stack for Cartesian Tree

## 33. Divide and Conquer - Top 50

Architect focus: Recursive decomposition, merge logic, recurrence analysis, and parallelizable thinking.

1. Merge Sort
2. Sort List
3. Kth Largest Element in an Array
4. Median of Two Sorted Arrays
5. Search a 2D Matrix II
6. Maximum Subarray
7. Different Ways to Add Parentheses
8. Construct Quad Tree
9. Convert Sorted Array to Binary Search Tree
10. Merge k Sorted Lists
11. Count of Smaller Numbers After Self
12. Reverse Pairs
13. The Skyline Problem
14. Closest Pair of Points
15. Pow(x, n)
16. Majority Element
17. Beautiful Array
18. Burst Balloons Interval Split
19. Expression Parsing by Operator Split
20. Parallel Merge
21. Quick Sort
22. Binary Search
23. Count of Range Sum
24. Convert Sorted List to Binary Search Tree
25. Build Binary Tree from Traversals
26. Karatsuba Multiplication
27. Strassen Matrix Multiplication
28. External Merge Sort
29. Parallel Merge Sort
30. K-way File Merge
31. Inversion Count
32. Small Sum
33. Merge Two Binary Search Trees
34. Find Peak Element
35. Kth Element of Two Sorted Arrays
36. Recursive Range Minimum Query
37. Segment Tree Build and Query
38. Sparse Table Build
39. Longest Duplicate Substring
40. Burst Balloons
41. Expression Add Operators
42. Boolean Parenthesization
43. Optimal Binary Search Tree
44. Matrix Chain Multiplication
45. Recursive Descent Expression Split
46. Divide-and-Conquer DP Optimization
47. Closest Subsequence Sum
48. Find K Closest Elements
49. Merge Intervals
50. Sort an Array

## 34. Combinatorics - Top 50

Architect focus: Counting arrangements, binomial coefficients, inclusion-exclusion, and modular counting.

1. Combinations
2. Combination Sum
3. Combination Sum II
4. Combination Sum III
5. Subsets
6. Permutations
7. Unique Paths
8. Unique Paths II
9. Climbing Stairs
10. Pascal Triangle
11. Pascal Triangle II
12. Count Sorted Vowel Strings
13. Number of Ways to Reorder Array to Get Same BST
14. Count Good Numbers
15. Beautiful Arrangement
16. K-th Symbol in Grammar
17. Unique Binary Search Trees
18. Derangements
19. Stars and Bars
20. Inclusion-Exclusion Divisible Counts
21. Letter Combinations of a Phone Number
22. Generate Parentheses
23. N-Queens II
24. Count Vowels Permutation
25. Number of Dice Rolls With Target Sum
26. Knight Dialer
27. Count Number of Teams
28. Number of Ways to Stay in the Same Place After Some Steps
29. Handshakes That Do Not Cross
30. Count All Valid Pickup and Delivery Options
31. Number of Sets of K Non-Overlapping Line Segments
32. Count Ways to Build Good Strings
33. Number of Music Playlists
34. Profitable Schemes
35. Student Attendance Record II
36. Number of Ways to Form a Target String Given a Dictionary
37. Count Anagrams
38. Count the Number of Ideal Arrays
39. Number of Ways to Divide a Long Corridor
40. Count Fertile Pyramids in a Land
41. Count Increasing Quadruplets
42. Count Special Subsequences
43. Count Subarrays With Fixed Bounds
44. Count Complete Subarrays in an Array
45. Count Pairs With XOR in a Range
46. Count the Number of Good Subarrays
47. Count of Smaller Numbers After Self
48. Reverse Pairs
49. K Inverse Pairs Array
50. Combination Iterator

## 35. Trie - Top 50

Architect focus: Prefix tree modeling, word search, autocomplete, wildcard search, and compressed storage trade-offs.

1. Implement Trie
2. Design Add and Search Words Data Structure
3. Word Search II
4. Replace Words
5. Map Sum Pairs
6. Longest Word in Dictionary
7. Search Suggestions System
8. Palindrome Pairs
9. Maximum XOR of Two Numbers in an Array
10. Stream of Characters
11. Concatenated Words
12. Word Squares
13. Prefix and Suffix Search
14. Camelcase Matching
15. Design Search Autocomplete System
16. Alien Dictionary Prefix Validation
17. Delete Word from Trie
18. Compressed Trie Autocomplete
19. Trie with Wildcard Dot
20. Trie-backed Router Matching
21. Word Break II
22. Word Ladder II
23. Short Encoding of Words
24. Implement Magic Dictionary
25. Longest Word With All Prefixes
26. Count Pairs With XOR in a Range
27. Maximum Genetic Difference Query
28. Design File System
29. Design In-Memory File System
30. Design Twitter Hashtag Autocomplete
31. Contacts Prefix Count
32. Phone Directory Prefix Search
33. IP Routing Longest Prefix Match
34. Binary Trie for Maximum XOR
35. Binary Trie for Minimum XOR Pair
36. Trie for Repeated DNA Sequences
37. Aho-Corasick Multiple Pattern Search
38. Trie for Boggle Board
39. Trie for Spell Checker
40. Trie for Search Suggestions with Ranking
41. Trie for Prefix Score Sum
42. Sum of Prefix Scores of Strings
43. Find Duplicate Folders in System
44. Remove Sub-Folders from the Filesystem
45. Longest Common Prefix
46. Longest Common Suffix with Reversed Trie
47. Wildcard Dictionary Search
48. Autocomplete with Hotness
49. Trie Serialization
50. Trie Memory Optimization

## 36. Bitmask - Top 50

Architect focus: Subset states, compressed DP, visited masks, permissions, and exponential-state control.

1. Subsets
2. Subsets II
3. Maximum Product of Word Lengths
4. Single Number
5. Counting Bits
6. Gray Code
7. Shortest Path Visiting All Nodes
8. Partition to K Equal Sum Subsets
9. Can I Win
10. Beautiful Arrangement
11. N-Queens Bitmask
12. Matchsticks to Square
13. Maximum Length of a Concatenated String with Unique Characters
14. Smallest Sufficient Team
15. Number of Squareful Arrays
16. Stickers to Spell Word
17. Traveling Salesman DP
18. Bitmask BFS with Keys
19. Permission Mask Design Problem
20. State Compression Grid DP
21. Minimum Number of Work Sessions to Finish the Tasks
22. Parallel Courses II
23. Maximum Students Taking Exam
24. Number of Ways to Wear Different Hats to Each Other
25. Shortest Path to Get All Keys
26. Find the Shortest Superstring
27. Maximum Compatibility Score Sum
28. Minimum Incompatibility
29. Distribute Repeating Integers
30. The Number of Good Subsets
31. Count Number of Maximum Bitwise-OR Subsets
32. Fair Distribution of Cookies
33. Beautiful Arrangement II
34. Sudoku Solver Bitmask
35. Word Search II with Bitmask Visited
36. Bitmask Hamiltonian Path
37. Bitmask Subset Sum
38. Bitmask Knapsack
39. Bitmask Assignment DP
40. Bitmask DP for Job Scheduling
41. Bitmask DP for Cap Assignment
42. Bitmask DP for Set Cover
43. Bitmask DP for Graph Coloring
44. Bitmask DP for Palindrome Partitioning
45. Bitmask DP for Domino Tiling
46. Bitmask DP for Grid Paths
47. Bitmask DP for Clique Cover
48. Bitmask DP for Independent Set
49. Bitmask DP for Steiner Tree
50. Bitmask DP for Team Selection

## 37. Queue - Top 49

Architect focus: FIFO processing, BFS, rate windows, buffering, and producer-consumer style reasoning.

1. Implement Queue using Stacks
2. Implement Stack using Queues
3. Number of Recent Calls
4. Design Circular Queue
5. Design Circular Deque
6. Moving Average from Data Stream
7. Sliding Window Maximum
8. Rotting Oranges
9. Walls and Gates
10. Open the Lock
11. Shortest Path in Binary Matrix
12. Jump Game III
13. Snakes and Ladders
14. Perfect Squares
15. Word Ladder
16. Bus Routes
17. Hit Counter
18. Task Scheduler Queue Simulation
19. Producer-Consumer Bounded Queue
20. Rate Limiter Queue Window
21. Design Hit Counter
22. Dota2 Senate
23. Reveal Cards In Increasing Order
24. Number of Students Unable to Eat Lunch
25. Time Needed to Buy Tickets
26. Design Front Middle Back Queue
27. Shortest Bridge
28. 01 Matrix
29. Minimum Genetic Mutation
30. Binary Tree Level Order Traversal
31. Binary Tree Zigzag Level Order Traversal
32. N-ary Tree Level Order Traversal
33. Average of Levels in Binary Tree
34. Find Largest Value in Each Tree Row
35. Minimum Depth of Binary Tree
36. Populating Next Right Pointers in Each Node
37. All Nodes Distance K in Binary Tree
38. As Far from Land as Possible
39. Shortest Path to Get All Keys
40. Sliding Puzzle
41. Race Car
42. The Maze
43. The Maze II
44. The Maze III
45. Multithreaded Bounded Blocking Queue
46. Web Crawler Multithreaded
47. Logger Rate Limiter
48. Number of Islands BFS
49. Multi-source Infection Spread

## 38. Recursion - Top 50

Architect focus: Base cases, recursion tree, call stack, divide/merge, and iterative conversion.

1. Climbing Stairs
2. Pow(x, n)
3. Merge Two Sorted Lists
4. Reverse Linked List
5. Swap Nodes in Pairs
6. Generate Parentheses
7. Subsets
8. Permutations
9. Combination Sum
10. N-Queens
11. Binary Tree Inorder Traversal
12. Maximum Depth of Binary Tree
13. Same Tree
14. Invert Binary Tree
15. Validate Binary Search Tree
16. Serialize and Deserialize Binary Tree
17. K-th Symbol in Grammar
18. Decode String
19. Different Ways to Add Parentheses
20. Recursive Descent Calculator
21. Fibonacci Number
22. Pascal Triangle
23. Pascal Triangle II
24. Tower of Hanoi
25. Merge Sort
26. Quick Sort
27. Binary Search Recursive
28. Path Sum
29. Path Sum II
30. Binary Tree Maximum Path Sum
31. Lowest Common Ancestor of a Binary Tree
32. Construct Binary Tree from Preorder and Inorder Traversal
33. Flatten Binary Tree to Linked List
34. Count Complete Tree Nodes
35. House Robber III
36. Word Search
37. Sudoku Solver
38. Palindrome Partitioning
39. Restore IP Addresses
40. Expression Add Operators
41. Beautiful Arrangement
42. Matchsticks to Square
43. Partition to K Equal Sum Subsets
44. Remove Invalid Parentheses
45. Letter Combinations of a Phone Number
46. Combinations
47. Combination Sum II
48. Subsets II
49. Permutations II
50. N-Queens II

## 39. Geometry - Top 50

Architect focus: Coordinates, distance, orientation, line sweep, convexity, and precision issues.

1. Max Points on a Line
2. Rectangle Overlap
3. Rectangle Area
4. Valid Square
5. Minimum Area Rectangle
6. Erect the Fence
7. K Closest Points to Origin
8. Robot Bounded In Circle
9. Mirror Reflection
10. Line Reflection
11. Detect Squares
12. Number of Boomerangs
13. Convex Polygon
14. Largest Triangle Area
15. Circle and Rectangle Overlapping
16. Check If It Is a Straight Line
17. Skyline Geometry
18. Closest Pair of Points
19. Segment Intersection
20. Point in Polygon
21. Minimum Area Rectangle II
22. Self Crossing
23. Ambiguous Coordinates
24. Random Point in Non-overlapping Rectangles
25. Generate Random Point in a Circle
26. Projection Area of 3D Shapes
27. Surface Area of 3D Shapes
28. Largest Perimeter Triangle
29. Minimum Time Visiting All Points
30. Valid Boomerang
31. Coordinate With Maximum Network Quality
32. Queries on Number of Points Inside a Circle
33. Maximum Number of Visible Points
34. Path Crossing
35. Escape The Ghosts
36. Robot Room Cleaner Geometry
37. Convex Hull Trick Line Container
38. Sweep Line Segment Intersection
39. Rectangle Area II
40. Number of Rectangles That Can Form the Largest Square
41. Minimum Lines to Represent a Line Chart
42. Check if It Is Possible to Split Array by Geometry
43. Line Sweep Closest Pair
44. Polygon Area Shoelace
45. Orientation Test CCW
46. Point on Segment
47. Ray Casting Point in Polygon
48. Rotating Calipers Diameter
49. Minimum Enclosing Circle
50. Circle Through Three Points

## 40. Binary Indexed Tree - Top 50

Architect focus: Fenwick tree prefix queries, point updates, coordinate compression, and inversion counting.

1. Range Sum Query - Mutable
2. Count of Smaller Numbers After Self
3. Reverse Pairs
4. Create Sorted Array through Instructions
5. Number of Longest Increasing Subsequence
6. Range Update Point Query
7. Point Update Range Query
8. Inversion Count
9. K-th Order Statistic with Fenwick
10. Coordinate Compression with Fenwick
11. 2D Fenwick Matrix Sum
12. Dynamic Frequency Table
13. Online Prefix Counts
14. Offline Greater-Than Queries
15. Fenwick lower_bound
16. Count of Range Sum
17. Queue Reconstruction by Height with BIT
18. Range Sum Query 2D - Mutable
19. Mutable Prefix XOR Query
20. Fenwick Tree for Frequency Ranking
21. Fenwick Tree for Order Statistics
22. Fenwick Tree for Dynamic Median
23. Fenwick Tree for Count Smaller After Self
24. Fenwick Tree for Count Greater Before Self
25. Fenwick Tree for Interval Stabbing Count
26. Fenwick Tree for Range Add Range Sum
27. Fenwick Tree for Point Assign Range Sum
28. Fenwick Tree for Difference Array
29. Fenwick Tree for K Empty Slots
30. Fenwick Tree for Calendar Sweep
31. Fenwick Tree for Longest Increasing Subsequence
32. Fenwick Tree for Maximum Prefix
33. Fenwick Tree for Minimum Prefix
34. Fenwick Tree for Distinct Values in Range
35. Fenwick Tree for Offline Range Queries
36. Fenwick Tree for Mo-like Updates
37. Fenwick Tree for 2D Points
38. Fenwick Tree for Rectangular Sum
39. Fenwick Tree for Dynamic Inversions
40. Fenwick Tree for Palindrome Queries
41. Fenwick Tree for Subtree Queries
42. Fenwick Tree over Euler Tour
43. Fenwick Tree for Path Queries
44. Fenwick Tree for H-Index Stream
45. Fenwick Tree for Top K Frequencies
46. Fenwick Tree for Rank Transform
47. Fenwick Tree for Range Product
48. Fenwick Tree for Modular Sum
49. Fenwick Tree for Compressed Timestamps
50. Fenwick Tree for Leaderboard Rankings

## 41. Hash Function - Top 50

Architect focus: Rolling hash, canonicalization, collision risk, dedupe, and checksum-style reasoning.

1. Group Anagrams
2. Valid Anagram
3. Repeated DNA Sequences
4. Find Duplicate File in System
5. Longest Duplicate Substring
6. Rabin-Karp Substring Search
7. Rolling Hash Palindrome Query
8. Isomorphic Strings
9. Word Pattern
10. Encode and Decode TinyURL
11. Design HashMap
12. Consistent Hashing
13. Content-Addressable Dedupe
14. Bloom Filter False Positives
15. Checksum Collision Discussion
16. Subdomain Visit Count
17. Analyze User Website Visit Pattern
18. Detect Squares
19. Max Points on a Line
20. Find Duplicate Subtrees
21. Equal Row and Column Pairs
22. String Compression with Hash
23. Minimum Window Substring Hash Variant
24. Distinct Echo Substrings
25. Shortest Palindrome
26. Repeated Substring Pattern
27. Substring with Concatenation of All Words
28. Find All Anagrams in a String
29. Permutation in String
30. Compare Version Numbers
31. Valid Sudoku Hashing
32. Group Shifted Strings
33. Jewels and Stones
34. Ransom Note
35. Contains Duplicate
36. Contains Duplicate II
37. Contains Duplicate III
38. Randomized Set Hashing
39. Randomized Collection Hashing
40. LRU Cache Key Hashing
41. LFU Cache Key Hashing
42. All O(1) Data Structure
43. Time Based Key-Value Store
44. Design File System Path Hashing
45. Find Duplicate Folders in System
46. Hash URL Shortener
47. MurmurHash Partitioning
48. Hash Ring Virtual Nodes
49. Hash Collision Attack Mitigation
50. Hash Canonicalization for Anagrams

## 42. Memoization - Top 50

Architect focus: Top-down DP, cache keys, overlapping subproblems, invalid states, and memory control.

1. Climbing Stairs
2. Coin Change
3. Word Break
4. Decode Ways
5. House Robber
6. Longest Increasing Subsequence
7. Edit Distance
8. Regular Expression Matching
9. Wildcard Matching
10. Interleaving String
11. Target Sum
12. Partition Equal Subset Sum
13. Can I Win
14. Stickers to Spell Word
15. Burst Balloons
16. Palindrome Partitioning II
17. Longest Common Subsequence
18. Minimum Path Sum
19. Dungeon Game
20. Scramble String
21. Fibonacci Number
22. Unique Paths
23. Unique Paths II
24. Triangle
25. Minimum Falling Path Sum
26. Paint House
27. Paint Fence
28. Combination Sum IV
29. Best Time to Buy and Sell Stock with Cooldown
30. Best Time to Buy and Sell Stock IV
31. Delete and Earn
32. Stone Game
33. Stone Game II
34. Stone Game III
35. Predict the Winner
36. Knight Dialer
37. Knight Probability in Chessboard
38. Soup Servings
39. New 21 Game
40. Shopping Offers
41. Profitable Schemes
42. Number of Dice Rolls With Target Sum
43. Minimum Cost For Tickets
44. Minimum Cost to Cut a Stick
45. Strange Printer
46. Remove Boxes
47. Cherry Pickup
48. Cherry Pickup II
49. Frog Jump
50. Word Break II

## 43. Binary Search Tree - Top 50

Architect focus: Ordered tree invariants, range search, insert/delete, balancing assumptions, and iterators.

1. Validate Binary Search Tree
2. Kth Smallest Element in a BST
3. Lowest Common Ancestor of a Binary Search Tree
4. Binary Search Tree Iterator
5. Insert into a BST
6. Delete Node in a BST
7. Recover Binary Search Tree
8. Convert Sorted Array to BST
9. Convert Sorted List to BST
10. Trim a Binary Search Tree
11. Range Sum of BST
12. Two Sum IV - Input is a BST
13. Closest Binary Search Tree Value
14. Balance a BST
15. Serialize and Deserialize BST
16. Split BST
17. BST Successor and Predecessor
18. AVL Tree Rotation
19. Red-Black Tree Insertion
20. Ordered Map Range Query
21. BST from Preorder
22. Search in a Binary Search Tree
23. Minimum Absolute Difference in BST
24. Find Mode in Binary Search Tree
25. Increasing Order Search Tree
26. All Elements in Two Binary Search Trees
27. Construct Binary Search Tree from Preorder Traversal
28. Convert BST to Greater Tree
29. Binary Search Tree to Greater Sum Tree
30. Maximum Sum BST in Binary Tree
31. Largest BST Subtree
32. Unique Binary Search Trees
33. Unique Binary Search Trees II
34. Recover Binary Search Tree with Morris Traversal
35. Inorder Successor in BST
36. Inorder Predecessor in BST
37. Closest Binary Search Tree Value II
38. Delete Nodes and Return Forest BST Variant
39. BST Range Iterator
40. BST Floor and Ceiling
41. BST Rank Query
42. BST Select Kth Query
43. Treap Insert Delete Search
44. Skiplist
45. Design Search Autocomplete with BST
46. Count of Smaller Numbers After Self using BST
47. Reverse Pairs using BST
48. Contains Duplicate III with TreeSet
49. My Calendar I with TreeMap
50. Range Module with TreeMap

## 44. Topological Sort - Top 50

Architect focus: DAG ordering, dependency resolution, cycle detection, and scheduling.

1. Course Schedule
2. Course Schedule II
3. Alien Dictionary
4. Minimum Height Trees
5. Find Eventual Safe States
6. Sequence Reconstruction
7. Sort Items by Groups Respecting Dependencies
8. Parallel Courses
9. Parallel Courses II
10. Build Matrix With Conditions
11. Loud and Rich
12. Recipe Dependencies
13. Task Scheduling with Prerequisites
14. Package Installation Order
15. Detect Cycle in Directed Graph
16. Kahn Algorithm
17. DFS Topological Sort
18. Lexicographically Smallest Topological Order
19. Critical Path in DAG
20. DAG Dynamic Programming
21. Course Schedule III
22. Course Schedule IV
23. All Ancestors of a Node in a Directed Acyclic Graph
24. Find Eventual Safe States via Reverse Graph
25. Minimum Number of Vertices to Reach All Nodes
26. Longest Increasing Path in a Matrix
27. Largest Color Value in a Directed Graph
28. Strange Printer II
29. Sequence Reconstruction Follow-up
30. Alien Dictionary with Invalid Prefix
31. Build System Dependency Order
32. Module Compilation Order
33. Workflow Execution Order
34. Job Scheduling with Dependencies
35. Topological Sort with Priority Queue
36. Topological Sort with Groups
37. Topological Sort With Cycle Reporting
38. Topological Sort With Multiple Valid Orders
39. Topological Sort Count Orders
40. Topological Sort for Prerequisite Closure
41. DAG Shortest Path
42. DAG Longest Path
43. DAG Path Count
44. DAG Transitive Closure
45. DAG Condensation Graph
46. SCC Condensation Topological Order
47. Find Champion II
48. Parallel Courses III
49. Prerequisite Queries with Bitsets
50. Topological Sort for Eventual Safe Nodes

## 45. Shortest Path - Top 50

Architect focus: BFS, Dijkstra, Bellman-Ford, Floyd-Warshall, state-expanded graphs, and weights.

1. Network Delay Time
2. Cheapest Flights Within K Stops
3. Path With Minimum Effort
4. Swim in Rising Water
5. Shortest Path in Binary Matrix
6. Word Ladder
7. Open the Lock
8. Bus Routes
9. Minimum Knight Moves
10. Dijkstra with State
11. Bellman-Ford Negative Edges
12. Floyd-Warshall All Pairs
13. A* Grid Pathfinding
14. 0-1 BFS
15. Shortest Path Visiting All Nodes
16. Minimum Cost to Make at Least One Valid Path in a Grid
17. Find the City With the Smallest Number of Neighbors
18. Reconstruct Itinerary Path
19. Evaluate Division Weighted Graph
20. The Maze II
21. The Maze III
22. Path with Maximum Probability
23. Minimum Weighted Subgraph With the Required Paths
24. Modify Graph Edge Weights
25. Reachable Nodes In Subdivided Graph
26. Number of Ways to Arrive at Destination
27. Minimum Cost to Reach Destination in Time
28. Second Minimum Time to Reach Destination
29. Shortest Path to Get All Keys
30. Race Car
31. Sliding Puzzle
32. Cut Off Trees for Golf Event
33. Minimum Obstacle Removal to Reach Corner
34. Minimum Cost to Make Valid Path in Grid
35. Shortest Bridge
36. As Far from Land as Possible
37. Nearest Exit from Entrance in Maze
38. Rotting Oranges
39. 01 Matrix
40. Walls and Gates
41. Word Ladder II
42. Bidirectional BFS Word Ladder
43. Dijkstra on Flights
44. Dijkstra on Grid
45. Dijkstra with K Stops
46. Multi-source BFS Distance
47. Dial Algorithm for Small Weights
48. SPFA Discussion Problem
49. Johnson All-Pairs Shortest Path
50. Shortest Cycle in a Graph

## 46. String Matching - Top 50

Architect focus: KMP, Z algorithm, trie, suffix structures, wildcard matching, and pattern preprocessing.

1. Find the Index of the First Occurrence in a String
2. Repeated Substring Pattern
3. Find All Anagrams in a String
4. Permutation in String
5. Minimum Window Substring
6. Rabin-Karp Substring Search
7. KMP Prefix Function
8. Z Algorithm Pattern Search
9. Wildcard Matching
10. Regular Expression Matching
11. Word Break
12. Word Search
13. Word Search II
14. Longest Duplicate Substring
15. Shortest Palindrome
16. Repeated DNA Sequences
17. String Compression Matching
18. Aho-Corasick Multiple Patterns
19. Suffix Array Substring Search
20. Trie Wildcard Search
21. Substring with Concatenation of All Words
22. Minimum Window Subsequence
23. Longest Happy Prefix
24. Implement strStr with KMP
25. Implement strStr with Rabin-Karp
26. Distinct Echo Substrings
27. Count Substrings That Differ by One Character
28. Number of Matching Subsequences
29. Find and Replace Pattern
30. Camelcase Matching
31. Expressive Words
32. Is Subsequence
33. Delete Operation for Two Strings
34. Edit Distance
35. Longest Common Subsequence
36. Longest Common Prefix
37. Longest Palindromic Substring
38. Palindromic Substrings
39. Palindrome Pairs
40. Word Pattern
41. Isomorphic Strings
42. Valid Anagram
43. Group Anagrams
44. Find Duplicate File in System
45. Check If a String Contains All Binary Codes of Size K
46. Check if One String Swap Can Make Strings Equal
47. Buddy Strings
48. Rotate String
49. String Matching in an Array
50. Find the Closest Palindrome

## 47. Rolling Hash - Top 50

Architect focus: Polynomial hashing, Rabin-Karp, collision handling, double hashing, and substring equality.

1. Repeated DNA Sequences
2. Longest Duplicate Substring
3. Rabin-Karp strStr
4. Shortest Palindrome
5. Distinct Echo Substrings
6. Check If a String Contains All Binary Codes of Size K
7. Palindrome Substring Hash Query
8. Substring Equality Queries
9. Find Duplicate Subtrees Hash Variant
10. 2D Rolling Hash Matrix Pattern
11. Double Hash Collision-Resistant Search
12. Rolling Hash with Deletion Window
13. Content Chunk Dedupe
14. Plagiarism Detector
15. Cyclic String Rotation Hash
16. Longest Happy Prefix
17. Repeated Substring Pattern
18. String Matching in an Array
19. Find All Anagrams in a String
20. Permutation in String
21. Minimum Window Substring Hash Variant
22. Longest Common Subpath
23. Find Substring With Given Hash Value
24. Sum of Scores of Built Strings
25. Number of Distinct Substrings in a String
26. Count Distinct Echo Substrings
27. Longest Repeating Substring
28. Rolling Hash for Palindrome Pairs
29. Rolling Hash for Word Break
30. Rolling Hash for Concatenated Words
31. Rolling Hash for Matrix Search
32. Rabin-Karp Multiple Pattern Search
33. Rolling Hash for Near-Duplicate Documents
34. Rolling Hash for File Dedupe
35. Rolling Hash for Log Chunking
36. Rolling Hash for DNA Motifs
37. Rolling Hash with Modular Inverse
38. Rolling Hash with Prefix Powers
39. Rolling Hash with Double Mod
40. Rolling Hash Collision Test
41. Rolling Hash for K-Length Substrings
42. Rolling Hash for Shortest Palindrome
43. Rolling Hash for Longest Prefix Suffix
44. Rolling Hash for Rotated Strings
45. Rolling Hash for Repeated Patterns
46. Rolling Hash for Anagram Windows
47. Rolling Hash for Subsequence Fingerprints
48. Rolling Hash for Stream Matching
49. Rolling Hash for Circular Buffer
50. Rolling Hash for Canonical Paths

## 48. Game Theory - Top 50

Architect focus: Winning states, minimax, DP on games, Sprague-Grundy ideas, and adversarial reasoning.

1. Nim Game
2. Can I Win
3. Predict the Winner
4. Stone Game
5. Stone Game II
6. Stone Game III
7. Stone Game IV
8. Divisor Game
9. Guess Number Higher or Lower II
10. Cat and Mouse
11. Flip Game II
12. Optimal Strategy for a Game
13. Minimax Tic-Tac-Toe
14. Grundy Number Take-Away Game
15. DP on Intervals Game
16. Winning State Graph Game
17. Adversarial Coin Row
18. Remove Boxes Game
19. Zuma Game
20. 24 Game
21. Stone Game V
22. Stone Game VI
23. Stone Game VII
24. Stone Game VIII
25. Stone Game IX
26. Stone Game X
27. Chalkboard XOR Game
28. Cat and Mouse II
29. Can I Win with Bitmask
30. Predict the Winner with Memoization
31. Nim Game II
32. Take Stones Until Losing
33. Coin Row Game
34. Deque Game
35. Substract a Square Game
36. Sprague-Grundy Mex Calculation
37. Green Hackenbush Intro Problem
38. Treblecross
39. Wythoff Game
40. Misere Nim
41. Game of Nim with Piles
42. Graph Game on DAG
43. Game on Tree Winning State
44. Minimax with Alpha-Beta
45. Tic Tac Toe Solver
46. Connect Four Minimax
47. Optimal Account Balancing Game Framing
48. Elimination Game
49. Dota2 Senate
50. Find the Winner of the Circular Game

## 49. Interactive - Top 50

Architect focus: Query strategy, binary search with feedback, invariant maintenance, and limited-call optimization.

1. Guess Number Higher or Lower
2. First Bad Version
3. Find Celebrity
4. Random Pick with Weight Interactive Reasoning
5. Binary Search with Yes-No Oracle
6. Find Local Minimum with Neighbor Queries
7. Guess the Word
8. Mastermind Feedback Minimization
9. Query-Limited Sorted Matrix Search
10. Unknown Size Array Binary Search
11. Interactive Graph Exploration
12. Noisy Oracle Majority Strategy
13. Adversarial Comparator Sorting
14. Limited API Iterator Validation
15. Online Median Query Design
16. Search in a Sorted Array of Unknown Size
17. Sparse Search with Empty Strings
18. Versioned API First Failure
19. Judge API for Celebrity
20. Guess Word Minimax
21. Find Hidden Array with Sum Queries
22. Find Hidden Permutation with Inversion Queries
23. Interactive Peak Finding
24. Interactive Tree Diameter
25. Interactive Bipartition
26. Interactive Shortest Path Oracle
27. Interactive Range Sum Query
28. Interactive K-th Element Query
29. Interactive Matrix Row Search
30. Interactive Sorted Rotated Search
31. Interactive Duplicate Finder
32. Interactive Majority Element
33. Interactive Lowest Common Ancestor
34. Interactive Network Discovery
35. Interactive Secret Propagation
36. Interactive Guess Distance
37. Interactive Hotter Colder
38. Interactive Black Box Testing
39. Interactive Rate-Limited Search
40. Interactive Binary Indexed Tree Query
41. Interactive Comparator Cycle Detection
42. Interactive Consistency Checker
43. Interactive API Pagination
44. Interactive Cursor Search
45. Interactive Feature Flag Bisect
46. Interactive Deployment Regression Bisect
47. Interactive Log Search
48. Interactive Database Lock Culprit Search
49. Interactive A/B Winner Search
50. Interactive Randomized Query Strategy

## 50. Data Stream - Top 44

Architect focus: Online algorithms, heaps, sketches, windows, approximations, and memory bounds.

1. Find Median from Data Stream
2. Kth Largest Element in a Stream
3. Moving Average from Data Stream
4. Data Stream as Disjoint Intervals
5. Number of Recent Calls
6. Logger Rate Limiter
7. Hit Counter
8. Top K Frequent Elements Stream
9. Sliding Window Maximum
10. Design Twitter Feed Stream
11. Reservoir Sampling
12. Random Pick Index
13. First Unique Number
14. Stream of Characters
15. Stock Price Fluctuation
16. Online Majority Element in Subarray
17. Approximate Distinct Count
18. Bloom Filter Stream Dedupe
19. Heavy Hitters Misra-Gries
20. Sliding Window Rate Limiter
21. Design Hit Counter
22. Last Stone Weight Stream Variant
23. Median Sliding Window
24. Sliding Window Median
25. Time Based Key-Value Store
26. Snapshot Array
27. Design a Leaderboard
28. Design Underground System
29. Recent Counter
30. First Unique Character in a Stream
31. Find First Non-Repeating Character in a Stream
32. Summary Ranges
33. Design Search Autocomplete System
34. Top K Frequent Words Stream
35. Count-Min Sketch Heavy Hitters
36. HyperLogLog Distinct Users
37. Reservoir Sample K from Stream
38. Rolling Window Counter
39. Exponential Moving Average
40. Online Variance Welford
41. Online Percentile Approximation
42. Online Min-Max Queue
43. Online Event Deduplication
44. Streaming Anomaly Counter

## 51. Monotonic Queue - Top 50

Architect focus: Deque invariants, sliding max/min, DP optimization, and amortized O(1) updates.

1. Sliding Window Maximum
2. Constrained Subsequence Sum
3. Shortest Subarray with Sum at Least K
4. Longest Continuous Subarray With Absolute Diff Less Than or Equal Limit
5. Jump Game VI
6. Max Value of Equation
7. Minimum Number of K Consecutive Bit Flips
8. Deque Max-Min Window
9. DP with Monotonic Deque
10. Stock Span Queue Variant
11. Queue Optimization for Knapsack
12. Max Subarray with Length Constraint
13. Min Queue Design
14. Queue with Max API
15. Streaming Rolling Maximum
16. Sliding Window Minimum
17. Monotonic Queue for Prefix Sum
18. Monotonic Queue for Shortest Subarray
19. Monotonic Queue for DP Optimization
20. Monotonic Queue for Convex Hull Trick Intro
21. Maximum Robots Within Budget
22. Find the Most Competitive Subsequence
23. Minimum Operations to Make Array Continuous
24. Continuous Subarrays
25. Longest Subarray with Limit
26. Maximum of Minimum for Every Window Size
27. Minimum of Maximum for Every Window Size
28. Deque-Based Rate Limiter
29. Deque-Based Time Window Aggregation
30. Moving Average with Min-Max
31. Online Temperature Range
32. Sliding Window Median Contrast
33. K Empty Slots with Window Min
34. Monotonic Queue for Stock Prices
35. Monotonic Queue for Jump Game
36. Monotonic Queue for Path DP
37. Monotonic Queue for Grid DP
38. Monotonic Queue for Bounded Knapsack
39. Monotonic Queue for Task Scheduling
40. Monotonic Queue for Event Streams
41. Monotonic Queue for Rolling SLA
42. Monotonic Queue for CPU Usage Window
43. Monotonic Queue for Latency Percentile Approximation
44. Monotonic Queue for Max Drawdown
45. Monotonic Queue for Peak Traffic
46. Monotonic Queue for Windowed Inventory
47. Monotonic Queue for Timeline Overlap
48. Monotonic Queue for Log Severity Window
49. Monotonic Queue for Rolling Leaderboard
50. Monotonic Queue for Windowed Distance

## 52. Brainteaser - Top 50

Architect focus: Invariants, paradoxes, probability, adversarial constraints, and clear communication.

1. Find Celebrity
2. Bulb Switcher
3. Nim Game
4. Prison Cells After N Days
5. Poor Pigs
6. Egg Drop Reasoning
7. 100 Doors
8. Two Eggs and 100 Floors
9. Water Jug Problem
10. Monty Hall
11. Clock Angle
12. Poisoned Bottle
13. Bridge and Torch
14. Hat Guessing Strategy
15. Random from Rand7
16. Majority Vote Proof
17. Counterfeit Coin
18. Adversarial Coin Flip
19. Expected Tosses Until Pattern
20. Invariant Chessboard Problem
21. Super Egg Drop
22. Elimination Game
23. Guess Number Higher or Lower II
24. Chalkboard XOR Game
25. Can I Win
26. Predict the Winner
27. Stone Game
28. Dota2 Senate
29. Find the Winner of the Circular Game
30. Josephus Problem
31. Airplane Seat Assignment Probability
32. New 21 Game
33. Soup Servings
34. Knight Probability in Chessboard
35. Random Pick with Weight
36. Implement Rand10 Using Rand7
37. Shuffle an Array
38. Reservoir Sampling Proof
39. Rejection Sampling Expected Attempts
40. Birthday Paradox
41. Coupon Collector
42. Prisoner Switch Puzzle
43. Light Bulb Switching
44. Rope Burning Puzzle
45. Clock Hands Overlap
46. Two Sum Without Addition
47. Sum of Two Integers
48. Power of Two Bit Trick
49. Single Number XOR Trick
50. Missing Number XOR Trick

## 53. Doubly-Linked List - Top 50

Architect focus: O(1) removal/insertion, cache design, sentinel nodes, and pointer consistency.

1. LRU Cache
2. LFU Cache
3. Flatten a Multilevel Doubly Linked List
4. Design Browser History
5. Design Linked List
6. All O(1) Data Structure
7. Insert into a Sorted Circular Linked List
8. Copy List with Random Pointer
9. Delete Node in a Doubly Linked List
10. Move Node to Front Cache Operation
11. Remove Tail in O(1)
12. Splice List Segment
13. Design Deque with Doubly Linked List
14. Undo-Redo Editor History
15. Least Recently Used Session Cache
16. Design Front Middle Back Queue
17. Design Circular Deque
18. Design Circular Queue
19. Browser History with Doubly Linked List
20. Deque with Doubly Linked List
21. Doubly Linked List Iterator
22. Doubly Linked List LRU Eviction
23. Doubly Linked List LFU Frequency Buckets
24. Doubly Linked List AllOne Buckets
25. Doubly Linked List Recent Items
26. Doubly Linked List Playlist
27. Doubly Linked List Text Editor
28. Doubly Linked List Page Cache
29. Doubly Linked List Free List Allocator
30. Doubly Linked List Timer Wheel Bucket
31. Doubly Linked List Ordered Cache
32. Doubly Linked List HashMap Integration
33. Doubly Linked List Node Removal
34. Doubly Linked List Node Insertion
35. Doubly Linked List Sentinel Nodes
36. Doubly Linked List Reverse
37. Doubly Linked List Merge
38. Doubly Linked List Split
39. Doubly Linked List Rotate
40. Doubly Linked List Swap Pairs
41. Doubly Linked List Sort
42. Doubly Linked List Flatten Tree
43. Doubly Linked List Multilevel Iterator
44. Doubly Linked List Browser Tabs
45. Doubly Linked List MRU Queue
46. Doubly Linked List Ordered Set
47. Doubly Linked List Skip Pointers
48. Doubly Linked List Memory Pool
49. Doubly Linked List Concurrent Access
50. Doubly Linked List Consistency Check

## 54. Merge Sort - Top 50

Architect focus: Stable divide-and-conquer sorting, inversion counting, linked-list sorting, and external merge.

1. Sort List
2. Merge Sorted Array
3. Merge Two Sorted Lists
4. Merge k Sorted Lists
5. Count of Smaller Numbers After Self
6. Reverse Pairs
7. Inversion Count
8. Maximum Subarray Divide and Conquer
9. External Merge Sort
10. Stable Sort Linked Records
11. Merge Intervals after Sort
12. Small Sum Problem
13. K-way File Merge
14. Sort Array with Merge Sort
15. Parallel Merge Sort
16. Count of Range Sum
17. Skyline Merge
18. Median of Two Sorted Arrays Merge Baseline
19. Merge Two Binary Search Trees
20. Merge Sort on Indexes
21. Sort an Array
22. Merge Sort
23. Divide Array into Sorted Runs
24. Natural Merge Sort
25. Bottom-Up Merge Sort
26. Top-Down Merge Sort
27. Merge Sort with Sentinel
28. Merge Sort for Linked List
29. Merge Sort for Large Files
30. Merge Sort with Limited Memory
31. Merge Sort Stability Test
32. Merge Sort Inversion Pairs
33. Merge Sort Important Reverse Pairs
34. Merge Sort Range Sum Count
35. Merge Sort Coordinate Compression
36. Merge Sort K Sorted Arrays
37. Merge Sort K Sorted Iterators
38. Merge Sort Log Files
39. Merge Sort Time Series Events
40. Merge Sort Intervals
41. Merge Sort Suffixes
42. Merge Sort Points by Coordinate
43. Merge Sort Custom Comparator
44. Merge Sort Parallel Merge Step
45. Merge Sort External Runs
46. Merge Sort Deduplicate
47. Merge Sort Count Smaller Before
48. Merge Sort Count Greater After
49. Merge Sort Stable Ranking
50. Merge Sort Multiway Merge

## 55. Randomized - Top 50

Architect focus: Random sampling, expected complexity, shuffling, randomized sets, and adversarial input resistance.

1. Insert Delete GetRandom O(1)
2. Random Pick Index
3. Random Pick with Weight
4. Shuffle an Array
5. Random Point in Non-overlapping Rectangles
6. Random Pick with Blacklist
7. Reservoir Sampling
8. Linked List Random Node
9. Generate Random Point in a Circle
10. Implement Rand10 using Rand7
11. Randomized Quickselect
12. Randomized Set with Duplicates
13. Weighted Reservoir Sample
14. Randomized Load Balancing
15. Randomized Treap
16. Randomized Collection
17. Random Flip Matrix
18. Random Pick with Weight Prefix Sum
19. Random Point in Circle Rejection Sampling
20. Random Point in Rectangle
21. Randomized Hashing
22. Randomized Majority Check
23. Randomized Min Cut Karger
24. Randomized Pivot Quicksort
25. Randomized Select Median
26. Randomized Skiplist
27. Design Skiplist
28. Randomized Load Balancer with Blacklist
29. Randomized A/B Assignment
30. Randomized Sampling from Stream
31. Randomized Sampling by Tenant
32. Randomized Cache Eviction
33. Randomized Backoff
34. Randomized Consistent Hashing
35. Randomized Test Case Generator
36. Randomized Differential Testing
37. Randomized Graph Sampling
38. Randomized Reservoir Merge
39. Randomized Weighted Choice
40. Randomized Round Robin
41. Randomized Hash Collision Defense
42. Randomized Quickselect Worst Case
43. Randomized Shuffle Proof
44. Randomized Permutation Generation
45. Randomized Subset Sampling
46. Randomized Pick Unique IDs
47. Randomized Event Sampling
48. Randomized Telemetry Sampling
49. Randomized Token Bucket Jitter
50. Randomized Retry Jitter

## 56. Counting Sort - Top 50

Architect focus: Bounded-domain sorting, frequency accumulation, stable placement, and memory trade-offs.

1. Sort Colors
2. Relative Sort Array
3. H-Index
4. Maximum Gap
5. Top K Frequent Elements
6. Sort Characters By Frequency
7. Counting Smaller Values in Bounded Range
8. Stable Counting Sort Implementation
9. Radix Sort Digit Counting
10. Sort Array by Parity Frequency
11. Bucket Frequency Ranking
12. Anagram Frequency Comparison
13. Counting Sort with Negative Numbers
14. Counting Sort Memory Trade-off
15. Linear Sort Event Timestamps
16. Height Checker
17. Sort Array By Increasing Frequency
18. Rank Transform of an Array
19. How Many Numbers Are Smaller Than the Current Number
20. Minimum Increment to Make Array Unique
21. Maximum Number of Coins You Can Get
22. Frequency Sort
23. Custom Sort String
24. Sort Integers by Number of 1 Bits
25. Sort the People
26. Counting Sort for Ages
27. Counting Sort for Grades
28. Counting Sort for ASCII Characters
29. Counting Sort for Lowercase Strings
30. Counting Sort for Timestamps in One Day
31. Counting Sort for IP Octets
32. Counting Sort for Small Integer Keys
33. Counting Sort for H-Index
34. Counting Sort for Top K Frequent
35. Counting Sort for Reconstruct Queue
36. Counting Sort for Meeting Times
37. Counting Sort for Log Severity
38. Counting Sort for Histogram Equalization
39. Counting Sort for Bucketed Latency
40. Counting Sort for Inventory Counts
41. Counting Sort for Character Replacement
42. Counting Sort for Valid Anagram
43. Counting Sort for Group Anagrams
44. Counting Sort for First Unique Character
45. Counting Sort for Ransom Note
46. Counting Sort for Jewels and Stones
47. Counting Sort for Max Balloons
48. Counting Sort for Frequency Comparison
49. Counting Sort for Relative Ranking
50. Counting Sort for Stable Placement

## 57. Iterator - Top 50

Architect focus: Lazy traversal, flattening, peeking, nested structures, and fail-fast semantics.

1. Peeking Iterator
2. Flatten Nested List Iterator
3. Binary Search Tree Iterator
4. Zigzag Iterator
5. Vector2D Iterator
6. RLE Iterator
7. Combination Iterator
8. Design Compressed String Iterator
9. Inorder Successor Iterator
10. Merge K Sorted Iterators
11. Paged API Iterator
12. Fail-Fast Iterator Design
13. Lazy Graph Traversal Iterator
14. Iterator with Remove Support
15. Time-Window Event Iterator
16. Nested Iterator
17. BST Iterator II
18. File System Iterator
19. Directory Tree Iterator
20. Trie Prefix Iterator
21. Sliding Window Iterator
22. Chunked Stream Iterator
23. Lookahead Iterator
24. Round-Robin Iterator
25. Interleaving Iterator
26. K-way Merge Iterator
27. Deduplicating Iterator
28. Filtering Iterator
29. Mapping Iterator
30. Batching Iterator
31. Rate-Limited Iterator
32. Backtracking Combination Iterator
33. Permutation Iterator
34. Subsets Iterator
35. Pagination Cursor Iterator
36. Database ResultSet Iterator
37. Kafka Consumer Iterator
38. Log File Line Iterator
39. Compressed Run-Length Iterator
40. Flatten Multilevel Doubly Linked List Iterator
41. Binary Tree Inorder Iterator
42. Binary Tree Preorder Iterator
43. Binary Tree Postorder Iterator
44. Graph BFS Iterator
45. Graph DFS Iterator
46. Range Iterator
47. Reverse Iterator
48. Skip Iterator
49. Peekable Stream Iterator
50. Iterator Consistency Under Mutation

## 58. Concurrency - Top 50

Architect focus: Thread coordination, synchronization, blocking queues, race prevention, and correctness under interleavings.

1. Print in Order
2. Print FooBar Alternately
3. Print Zero Even Odd
4. Building H2O
5. Fizz Buzz Multithreaded
6. Design Bounded Blocking Queue
7. The Dining Philosophers
8. Web Crawler Multithreaded
9. Thread-safe LRU Cache
10. Producer-Consumer Queue
11. Readers-Writer Lock
12. Rate Limiter with Concurrent Requests
13. Concurrent Hit Counter
14. Barrier Implementation
15. Deadlock Prevention Lock Ordering
16. Semaphore-based Connection Pool
17. Thread-safe Queue
18. Thread-safe Stack
19. Thread-safe HashMap
20. Thread-safe Singleton
21. Dining Philosophers with Semaphores
22. H2O with Semaphores
23. Print Odd Even with Conditions
24. Print ABC in Order
25. Cyclic Barrier from Scratch
26. CountDownLatch from Scratch
27. Blocking Queue with ReentrantLock
28. Blocking Queue with wait/notify
29. Bounded Buffer Problem
30. Async Task Scheduler
31. Thread Pool from Scratch
32. Work Stealing Queue
33. Concurrent Web Crawler
34. Concurrent File Downloader
35. Concurrent Rate Limiter
36. Concurrent Token Bucket
37. Concurrent LRU Cache
38. Concurrent LFU Cache
39. Concurrent Logger
40. Concurrent Metrics Aggregator
41. Concurrent Bank Transfer Deadlock
42. Optimistic Locking Counter
43. CAS-based Counter
44. ReadWriteLock Cache
45. Striped Lock HashMap
46. Lock-Free Stack ABA Problem
47. Producer-Consumer with Poison Pill
48. Scheduled Executor Design
49. Timer Wheel Concurrent Scheduler
50. ForkJoin Parallel Merge Sort

## 59. Suffix Array - Top 50

Architect focus: Suffix ordering, LCP, substring search, repeated substrings, and string indexing.

1. Longest Duplicate Substring
2. Repeated Substring Pattern
3. Longest Repeated Substring
4. Distinct Substrings Count
5. Substring Search with Suffix Array
6. LCP Array Construction
7. Smallest Cyclic Shift
8. Longest Common Substring of Two Strings
9. Pattern Count with Binary Search on Suffix Array
10. Suffix Array for Log Search
11. Burrows-Wheeler Transform
12. K-th Lexicographic Substring
13. Palindrome Query with Suffix Structures
14. Suffix Automaton Comparison
15. DNA Sequence Index
16. Suffix Array Doubling Algorithm
17. Suffix Array SA-IS Intro
18. Kasai LCP Algorithm
19. Number of Distinct Substrings
20. Longest Palindromic Substring via Suffix Array
21. Longest Common Prefix Queries
22. Repeated DNA Sequences
23. Shortest Palindrome
24. String Matching in an Array
25. Find All Occurrences of Pattern
26. Suffix Array for Multiple Strings
27. Suffix Array for Plagiarism Detection
28. Suffix Array for Genome Assembly
29. Suffix Array for Autocomplete
30. Suffix Array for Compression
31. Suffix Array for BWT Inversion
32. Suffix Array with RMQ
33. Suffix Array Longest Common Prefix of K Strings
34. Suffix Array Minimal Rotation
35. Suffix Array Lexicographic Rank
36. Suffix Array Pattern Lower Bound
37. Suffix Array Pattern Upper Bound
38. Suffix Array Distinct Echo Substrings
39. Suffix Array Longest Tandem Repeat
40. Suffix Array Common Subpath
41. Suffix Array Duplicate Code Detection
42. Suffix Array Search Suggestions
43. Suffix Array Keyword Search
44. Suffix Array Text Index
45. Suffix Array Query Engine
46. Suffix Array External Memory
47. Suffix Array Unicode Strings
48. Suffix Array Compressed Index
49. Suffix Array vs Trie
50. Suffix Array vs Rolling Hash

## 60. Quickselect - Top 50

Architect focus: Selection, partitioning, expected linear time, pivot choice, and worst-case risk.

1. Kth Largest Element in an Array
2. K Closest Points to Origin
3. Top K Frequent Elements
4. Median of Unsorted Array
5. Wiggle Sort II
6. Kth Smallest Element in an Array
7. Kth Largest Stream Contrast
8. Quickselect with Duplicates
9. Three-Way Partition Selection
10. Deterministic Median of Medians
11. Partial Sort Top K
12. Select Percentile Latency
13. Random Pivot Adversarial Input
14. In-place Kth Order Statistic
15. Find K Closest Elements
16. Kth Smallest Pair Distance
17. Kth Smallest Prime Fraction
18. Kth Smallest Element in a Sorted Matrix
19. Kth Largest Element with Heap Contrast
20. Kth Largest Element with Sorting Contrast
21. Partition Around Pivot
22. Dutch National Flag Quickselect
23. Quickselect for Median
24. Quickselect for Quantiles
25. Quickselect for P95 Latency
26. Quickselect for Kth Frequency
27. Quickselect for K Nearest Points
28. Quickselect for K Lowest Costs
29. Quickselect for K Highest Scores
30. Quickselect for Top K Words
31. Quickselect for Top K Logs
32. Quickselect for Order Statistics Tree Contrast
33. Quickselect Worst Case
34. Quickselect Average Case
35. Quickselect Tail Recursion
36. Quickselect Iterative
37. Quickselect Stable Not Guaranteed
38. Quickselect with Randomized Pivot
39. Quickselect with Median-of-Three Pivot
40. Quickselect with Introselect
41. Quickselect for Sparse Vectors
42. Quickselect for Recommendations
43. Quickselect for Leaderboard Trim
44. Quickselect for Batch Analytics
45. Quickselect for Reservoir Sample Trim
46. Quickselect for Kth Missing Number
47. Quickselect for Kth Distance
48. Quickselect for Kth Product
49. Quickselect for Kth Sum
50. Quickselect for Weighted Median

## 61. Sweep Line - Top 50

Architect focus: Events, active set, interval overlap, geometry intersections, and time-ordered state.

1. Meeting Rooms
2. Meeting Rooms II
3. Merge Intervals
4. Insert Interval
5. Non-overlapping Intervals
6. Minimum Number of Arrows to Burst Balloons
7. Car Pooling
8. Corporate Flight Bookings
9. My Calendar I
10. My Calendar II
11. My Calendar III
12. The Skyline Problem
13. Employee Free Time
14. Rectangle Area II
15. Number of Airplanes in the Sky
16. Interval List Intersections
17. K Empty Slots
18. Maximum Population Year
19. Line Segment Intersection
20. Active Set Closest Pair
21. Amount of New Area Painted Each Day
22. Minimum Interval to Include Each Query
23. Number of Flowers in Full Bloom
24. Describe the Painting
25. Perfect Rectangle
26. Falling Squares
27. Range Module
28. Count Positions on Street With Required Brightness
29. Find Right Interval
30. Minimum Meeting Rooms
31. Meeting Scheduler
32. Calendar Triple Booking
33. Sweep Line for CPU Load
34. Sweep Line for Bandwidth Usage
35. Sweep Line for Hotel Bookings
36. Sweep Line for Flight Bookings
37. Sweep Line for Timeline Concurrency
38. Sweep Line with Difference Array
39. Sweep Line with Ordered Set
40. Sweep Line with Segment Tree
41. Sweep Line for Union of Intervals
42. Sweep Line for Rectangle Union Area
43. Sweep Line for Closest Pair
44. Sweep Line for Intersections
45. Sweep Line for Overlapping Circles
46. Sweep Line for Event Scheduler
47. Sweep Line for Log Sessions
48. Sweep Line for User Online Time
49. Sweep Line for Resource Allocation
50. Sweep Line for Conflict Detection

## 62. Probability and Statistics - Top 50

Architect focus: Expected value, random processes, distributions, sampling, and estimation.

1. Random Pick with Weight
2. Random Pick Index
3. Shuffle an Array
4. Reservoir Sampling
5. Implement Rand10 using Rand7
6. Random Point in Circle
7. Random Point in Non-overlapping Rectangles
8. Poor Pigs
9. New 21 Game
10. Soup Servings
11. Knight Probability in Chessboard
12. Dice Roll Simulation
13. Probability of a Two Boxes Having Same Number of Distinct Balls
14. Expected Retries in Rejection Sampling
15. A/B Test Sample Size Reasoning
16. Heavy Hitters Estimation
17. Count-Min Sketch Reasoning
18. HyperLogLog Cardinality Estimate
19. Weighted Random Load Balancing
20. Monte Carlo Pi Estimation
21. Airplane Seat Assignment Probability
22. Random Pick with Blacklist
23. Linked List Random Node
24. Random Flip Matrix
25. Random Point in Rectangles
26. Binomial Distribution Problem
27. Geometric Distribution Expected Trials
28. Coupon Collector
29. Birthday Paradox
30. Expected Tosses Until Pattern
31. Markov Chain Intro Problem
32. Bayesian Update Problem
33. Confidence Interval for Conversion Rate
34. P-value Interpretation
35. Reservoir Sampling Proof
36. Rejection Sampling Bias Test
37. Weighted Reservoir Sampling
38. Stratified Sampling
39. Systematic Sampling
40. Online Mean Variance Welford
41. Streaming Quantile Approximation
42. Median from Data Stream
43. Sliding Window Median
44. Approximate Distinct Count
45. Bloom Filter False Positive Rate
46. Count-Min Sketch Error Bound
47. Randomized A/B Assignment
48. Thompson Sampling Intro
49. Multi-Armed Bandit Basic
50. Monte Carlo Integration

## 63. Minimum Spanning Tree - Top 49

Architect focus: Kruskal, Prim, cut/cycle properties, DSU, and network design analogies.

1. Min Cost to Connect All Points
2. Connecting Cities With Minimum Cost
3. Optimize Water Distribution in a Village
4. Network Connection MST
5. Critical and Pseudo-Critical Edges in MST
6. Kruskal Implementation
7. Prim Implementation
8. Union-Find Cycle Test
9. Minimum Cost to Supply Offices
10. Cluster Points by MST Threshold
11. Maximum Spacing Clustering
12. MST with Pre-connected Nodes
13. MST After Sorting Edges
14. MST with Manhattan Distance
15. MST vs Shortest Path Comparison
16. Find Critical and Pseudo-Critical Edges in Minimum Spanning Tree
17. Minimum Cost to Connect Sticks Contrast
18. Last Day Where You Can Still Cross MST Contrast
19. Swim in Rising Water MST Approach
20. Path With Minimum Effort MST Approach
21. Minimum Cost to Connect All Cities
22. Kruskal with Existing Roads
23. Prim with Dense Graph
24. Prim with Sparse Graph
25. MST for Network Cabling
26. MST for Data Center Links
27. MST for Clustering Services
28. MST with Forbidden Edges
29. MST with Required Edges
30. Second Best MST
31. Minimum Bottleneck Spanning Tree
32. Maximum Spanning Tree
33. MST Edge Classification
34. MST Under Edge Updates
35. Dynamic MST Intro
36. MST with Euclidean Points
37. MST with Complete Graph Optimization
38. MST with Disconnected Graph
39. MST Validity Check
40. MST Cut Property Problem
41. MST Cycle Property Problem
42. MST with Equal Weights
43. MST Lexicographic Tie-Break
44. MST for Image Segmentation
45. MST for Road Repair
46. MST for Power Grid
47. MST for Region Partitioning
48. MST for Communication Network
49. MST Rebuild After Failure

## 64. Bucket Sort - Top 50

Architect focus: Distribution-aware sorting, bucket design, hashing/ranges, and linear-time assumptions.

1. Top K Frequent Elements
2. Sort Characters By Frequency
3. Maximum Gap
4. Contains Duplicate III Bucket Variant
5. H-Index
6. Bucketed Rate Limiter
7. Bucket by Value Ranges
8. Bucket by Timestamps
9. Linear Sort Floats in Range
10. Group Logs by Timestamp Bucket
11. Frequency Bucket Leaderboard
12. Bucket Sort with Skew Handling
13. Bucket Sort Memory Trade-off
14. Bucketized Nearest Neighbor
15. Bucket Sort External Partitions
16. Sort Colors
17. Relative Sort Array
18. Rank Transform of an Array
19. How Many Numbers Are Smaller Than the Current Number
20. Maximum Gap with Buckets
21. Pigeonhole Principle Bucket Problem
22. Bucket Sort for Ages
23. Bucket Sort for Grades
24. Bucket Sort for Scores
25. Bucket Sort for IP Ranges
26. Bucket Sort for Latency Histograms
27. Bucket Sort for Event Time Windows
28. Bucket Sort for Rate Limiter Windows
29. Bucket Sort for Top K Frequencies
30. Bucket Sort for Anagram Lengths
31. Bucket Sort for Character Frequencies
32. Bucket Sort for Floating Values
33. Bucket Sort for Uniform Distribution
34. Bucket Sort for Sparse Distribution
35. Bucket Sort with Linked Buckets
36. Bucket Sort with Dynamic Buckets
37. Bucket Sort for Log Severity
38. Bucket Sort for Percentiles
39. Bucket Sort for Approximate Median
40. Bucket Sort for K Closest Points by Distance Bucket
41. Bucket Sort for Calendar Days
42. Bucket Sort for Time Series Rollup
43. Bucket Sort for Histogram Equalization
44. Bucket Sort for Counting Inversions Contrast
45. Bucket Sort for Max Consecutive Gap
46. Bucket Sort for Radix Pass
47. Bucket Sort for External Shuffle
48. Bucket Sort for Distributed Partitioning
49. Bucket Sort for Load Balancing
50. Bucket Sort for Consistent Hash Ranges

## 65. Shell - Top 50

Architect focus: Gap-based insertion sorting, diminishing increments, cache behavior, and algorithm comparison.

1. Shell Sort
2. Shell Sort with Ciura Gap Sequence
3. Shell Sort with Knuth Gap Sequence
4. Shell Sort on Nearly Sorted Array
5. Gapped Insertion Sort
6. Sort an Array
7. Insertion Sort List
8. Sort List
9. Sort Colors
10. Relative Sort Array
11. Maximum Gap
12. H-Index
13. Top K Frequent Elements
14. Sort Characters By Frequency
15. Reorder Data in Log Files
16. Largest Number
17. Wiggle Sort II
18. Merge Sorted Array
19. Merge Intervals
20. Counting Sort
21. Radix Sort Integers
22. Bucket Sort Floating Values
23. External Sort Run Generation
24. TimSort Run Detection
25. Partial Sort Top K
26. Shell Sort Gap Sequence Analysis
27. Shell Sort Worst-Case Input
28. Shell Sort Best-Case Input
29. Shell Sort Stability Discussion
30. Shell Sort In-Place Sorting
31. Shell Sort for Embedded Systems
32. Shell Sort Cache Behavior
33. Shell Sort vs Insertion Sort
34. Shell Sort vs Heap Sort
35. Shell Sort vs Quick Sort
36. Shell Sort for Small Arrays
37. Shell Sort for Partially Sorted Logs
38. Shell Sort with Tokuda Gaps
39. Shell Sort with Sedgewick Gaps
40. Shell Sort with Pratt Gaps
41. Shell Sort for Fixed-Size Records
42. Shell Sort for Memory-Constrained Sorting
43. Shell Sort for Nearly Sorted Time Series
44. Shell Sort Implementation Bug Hunt
45. Shell Sort Complexity Proof Sketch
46. Shell Sort Gap Benchmark
47. Shell Sort Generic Comparator
48. Shell Sort Descending Order
49. Shell Sort Duplicate Keys
50. Shell Sort Negative Numbers

## 66. Reservoir Sampling - Top 50

Architect focus: Uniform streaming sample, unknown length, weighted sampling, and proof of probability.

1. Linked List Random Node
2. Random Pick Index
3. Reservoir Sample One Item
4. Reservoir Sample K Items
5. Weighted Reservoir Sampling
6. Distributed Reservoir Merge
7. Streaming Log Sampling
8. Random Line from Huge File
9. Sample Events Under Memory Limit
10. Per-Tenant Reservoir Sampling
11. Time-Decayed Reservoir Sampling
12. Stratified Reservoir Sampling
13. Sliding-Window Reservoir Sampling
14. Priority Reservoir Sampling
15. A-Res Weighted Sampling
16. Sample Kafka Events Uniformly
17. Sample Clickstream Events
18. Sample Telemetry Traces
19. Sample Requests Per Endpoint
20. Sample Per User Session
21. Merge Two Reservoirs
22. Reservoir Sampling With Replacement
23. Reservoir Sampling Without Replacement
24. Reservoir Sampling for Infinite Stream
25. Uniform Sample from Iterator
26. Random Node in Linked List
27. Random Pick with Weight
28. Shuffle an Array
29. Random Pick with Blacklist
30. Implement Rand10 Using Rand7
31. Random Point in Non-overlapping Rectangles
32. Random Point in Circle
33. Reservoir Sample Distinct Users
34. Reservoir Sample Weighted Events
35. Reservoir Sample Per Shard
36. Reservoir Sample Across Partitions
37. Reservoir Sampling Proof of Uniformity
38. Reservoir Sampling Unknown Stream Length
39. Reservoir Sampling with Deletions
40. Reservoir Sampling with TTL
41. Reservoir Sampling for Distributed Tracing
42. Reservoir Sampling for Logs
43. Reservoir Sampling for Metrics
44. Reservoir Sampling with Priority Keys
45. Reservoir Sampling with Tenant Quotas
46. Reservoir Sampling with Backpressure
47. Reservoir Sampling with Mergeable State
48. Reservoir Sampling K from N Proof
49. Reservoir Sampling Online Replacement
50. Reservoir Sampling for A/B Events

## 67. Eulerian Circuit - Top 50

Architect focus: In/out degree conditions, Hierholzer, itinerary reconstruction, and edge-once traversal.

1. Reconstruct Itinerary
2. Valid Arrangement of Pairs
3. Cracking the Safe
4. Hierholzer Algorithm
5. Eulerian Path in Directed Graph
6. Eulerian Circuit in Undirected Graph
7. Use All Tickets Exactly Once
8. De Bruijn Sequence
9. Route Inspection Problem
10. Chinese Postman Problem
11. Lexicographically Smallest Euler Path
12. Euler Path With Duplicate Edges
13. Euler Circuit With Disconnected Components
14. Find Start Node for Euler Path
15. Edge-Once Log Traversal
16. Mail Delivery Route
17. Genome Assembly with De Bruijn Graph
18. Domino Chain Arrangement
19. Word Chain Euler Path
20. Itinerary Reconstruction with Priority Queues
21. Directed In-Out Degree Validation
22. Undirected Odd Degree Validation
23. Euler Path in Semi-Eulerian Graph
24. Euler Circuit Existence Check
25. Euler Path Connectivity Check
26. Euler Path with Multigraph
27. Euler Path with Self-Loops
28. Euler Path with Parallel Edges
29. Euler Tour in Tree
30. Euler Tour for Subtree Queries
31. Euler Trail for Street Sweeper
32. Eulerian Cycle in Directed Multigraph
33. Eulerian Path in Flight Tickets
34. Eulerian Path with Lexicographic Tie
35. Eulerian Circuit with Stack Implementation
36. Eulerian Circuit Recursive DFS
37. Eulerian Path Failure Cases
38. Eulerian Circuit for DNA k-mers
39. Eulerian Trail for Network Packets
40. Eulerian Path for Audit Log Chain
41. Eulerian Circuit Edge Removal Pitfall
42. Eulerian Path Start-End Selection
43. Eulerian Circuit Verification
44. Eulerian Path Reconstruction from Edge List
45. Eulerian Circuit in Sparse Graph
46. Eulerian Circuit in Dense Graph
47. Eulerian Trail with Isolated Vertices
48. Eulerian Path in Undirected Multigraph
49. Eulerian Circuit with Priority Queue
50. Eulerian Path with Postorder Stack

## 68. Radix Sort - Top 50

Architect focus: Digit-wise sorting, stable counting sort, integer/string keys, and linear-time constraints.

1. Maximum Gap
2. Radix Sort Integers
3. Radix Sort Strings
4. Sort Fixed-Length IDs
5. Sort Variable-Length Strings
6. LSD Radix Sort
7. MSD Radix Sort
8. Counting Sort as Radix Subroutine
9. Handle Negative Integers
10. Sort IP Addresses
11. Sort Timestamps
12. Sort UUID-like Keys
13. Radix Sort Memory Trade-off
14. External Radix Partitioning
15. Compare Radix vs Comparison Sort
16. Sort Colors via Counting Pass
17. Relative Sort Array
18. Sort Array By Increasing Frequency
19. H-Index with Counting
20. Maximum Gap with Radix
21. Radix Sort Base 10
22. Radix Sort Base 256
23. Radix Sort for Signed Integers
24. Radix Sort for Long Values
25. Radix Sort for Decimal Strings
26. Radix Sort for Lexicographic Codes
27. Radix Sort for Dates
28. Radix Sort for Log Timestamps
29. Radix Sort for Phone Numbers
30. Radix Sort for Product IDs
31. Radix Sort for Fixed Width Keys
32. Radix Sort for Variable Width Keys
33. Radix Sort with Stable Counting Sort
34. Radix Sort with Buckets
35. Radix Sort in External Memory
36. Radix Sort Distributed Shuffle
37. Radix Sort for Sparse IDs
38. Radix Sort for Dense IDs
39. Radix Sort for Unicode Strings
40. Radix Sort for Lowercase Strings
41. Radix Sort for File Names
42. Radix Sort for IP Ranges
43. Radix Sort for Network Prefixes
44. Radix Sort for Binary Strings
45. Radix Sort for Hex Strings
46. Radix Sort for Leaderboard Scores
47. Radix Sort for Event Sequence Numbers
48. Radix Sort for Version Numbers
49. Radix Sort Stability Test
50. Radix Sort Complexity Analysis

## 69. Strongly Connected Component - Top 50

Architect focus: Kosaraju, Tarjan, condensation DAG, cycle groups, and dependency analysis.

1. Tarjan Strongly Connected Components
2. Kosaraju Strongly Connected Components
3. Condensation Graph
4. 2-SAT Satisfiability
5. Find Eventual Safe States
6. Course Schedule Cycle Groups
7. Package Dependency Cycles
8. Deadlock Cycle Groups
9. Minimum Edges to Strongly Connect Graph
10. Mother Vertex
11. Strongly Connected City Roads
12. Reachability Compression in Directed Graph
13. SCC Topological Order
14. Low-Link Values in Directed Graph
15. Web Crawler Component Compression
16. Social Graph Mutual Reachability
17. Compiler Module Cycles
18. Build System Cycles
19. Directed Graph Cycle Decomposition
20. Minimum Starting Nodes in DAG of SCCs
21. Largest Color Value in a Directed Graph
22. Critical Connections Contrast
23. Course Schedule
24. Course Schedule II
25. Alien Dictionary Cycle Detection
26. Minimum Number of Vertices to Reach All Nodes
27. Find Eventual Safe States via SCC
28. 2-SAT Variable Implication Graph
29. SCC Condensation DAG Path Count
30. SCC for Workflow Cycles
31. SCC for Service Dependency Cycles
32. SCC for Import Graph
33. SCC for Strong Connectivity Check
34. SCC for One-Way Roads
35. SCC for Deadlock Detection
36. SCC for Transaction Wait Graph
37. SCC for Web Pages
38. SCC for Graph Compression
39. SCC for Tournament Graphs
40. SCC for Dominating Components
41. SCC Low-Link Iterative
42. SCC with Stack Membership
43. SCC with Reverse Graph
44. SCC with Postorder
45. SCC Component IDs
46. SCC Source Components
47. SCC Sink Components
48. SCC Minimum Edges to Add
49. SCC Reachability Queries
50. SCC Condensed Topological Sort

## 70. Rejection Sampling - Top 50

Architect focus: Sampling from constrained distributions, acceptance probability, bias, and efficiency.

1. Implement Rand10 Using Rand7
2. Random Point in a Circle
3. Avoid Modulo Bias
4. Uniform Integer from Biased Source
5. Sample Point Inside Polygon
6. Random Pick with Blacklist
7. Random Pick with Weight
8. Generate Random Point Under Constraint
9. Acceptance-Rejection for Normal Distribution
10. Rejection Sampling Expected Attempts
11. Monte Carlo Constrained Simulation
12. Sample From Disk Using Bounding Box
13. Sample From Triangle Using Rejection
14. Weighted Rejection Sampler
15. Bounded Retry Sampler
16. Production Random Sampler Validation
17. Bias Detection in Random Sampler
18. Rejection Sampling With Sparse Valid IDs
19. Uniform Coupon Sampler
20. Random Valid Grid Cell
21. Rand7 to Rand10 with Rejection
22. Rand5 to Rand7
23. Uniform Die from Coin
24. Random Integer Excluding Blacklist
25. Random Point in Non-overlapping Rectangles
26. Random Point in Circle by Rejection
27. Random Pick with Rejection Cache
28. Rejection Sampling for Tenant Quotas
29. Rejection Sampling for Filtered Events
30. Rejection Sampling for Active Users
31. Rejection Sampling for Valid IDs
32. Rejection Sampling Acceptance Rate
33. Rejection Sampling with Retry Budget
34. Rejection Sampling with Fallback
35. Rejection Sampling Bias Analysis
36. Rejection Sampling for Weighted Distribution
37. Rejection Sampling for Discrete Distribution
38. Rejection Sampling for Continuous Distribution
39. Rejection Sampling with Bounding Box
40. Rejection Sampling for Random Password Policy
41. Rejection Sampling for Random Graph Edge
42. Rejection Sampling for Random Matrix Cell
43. Rejection Sampling for Random Free Seat
44. Rejection Sampling for Random Available Slot
45. Rejection Sampling for Random Inventory Item
46. Rejection Sampling for Random Geo Point
47. Rejection Sampling for Non-overlapping Shapes
48. Rejection Sampling for Monte Carlo Integration
49. Rejection Sampling for Load Test Users
50. Rejection Sampling for AB Assignment

## 71. Biconnected Component - Top 50

Architect focus: Articulation points, bridges, low-link values, resilience, and block-cut trees.

1. Critical Connections in a Network
2. Articulation Points
3. Find Bridges in an Undirected Graph
4. Tarjan Biconnected Components
5. Block-Cut Tree
6. Bridge-Connected Components
7. Two-Vertex-Connected Graph Check
8. Network Resilience After Node Removal
9. Router Failure Impact Analysis
10. Road Network Articulation Points
11. Data Center Topology Resilience
12. Low-Link DFS for Undirected Graph
13. Edge Stack for Biconnected Components
14. Recover Components After Articulation Removal
15. Minimum Edges to Make Network Biconnected
16. Bridge Tree Diameter
17. Find All Cut Vertices
18. Find All Cut Edges
19. Biconnected Component Decomposition
20. Graph Valid Tree
21. Bridge Finding with Tarjan
22. Articulation Point Root Case
23. Articulation Point Non-root Case
24. Biconnected Components with Edge Stack
25. Block-Cut Tree Queries
26. Bridge Tree Construction
27. 2-Edge-Connected Components
28. 2-Vertex-Connected Components
29. Network Critical Routers
30. Critical Connections Follow-up
31. Remove One Node Connectivity
32. Remove One Edge Connectivity
33. Undirected Low-Link Values
34. DFS Discovery Low Arrays
35. Biconnected Component IDs
36. Biconnected Component Count
37. Minimum New Edges for 2-Edge Connectivity
38. Minimum New Edges for 2-Vertex Connectivity
39. Bridge Tree Leaf Count
40. Articulation Points in Road Map
41. Articulation Points in Data Center
42. Biconnected Components in Social Graph
43. Bridge Edges in Network
44. Critical Links in Cluster
45. Resilient Network Design
46. Failure Domain Decomposition
47. Biconnected Component Query
48. Block-Cut Tree LCA
49. Tarjan Undirected Graph Template
50. Biconnected Component Stress Test

## Final DSA Interview Drill

Before any coding round, pick one problem each from Array, Hash Table, Two Pointers, Sliding Window, Stack, Heap, Binary Search, Tree, Graph, Dynamic Programming, Greedy, Backtracking, Union-Find, and Design. Explain the production analogy before writing code. If you cannot explain why the pattern works, do not count the problem as solved.