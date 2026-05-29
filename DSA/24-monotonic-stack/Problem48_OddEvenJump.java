import java.util.*;

/**
 * Problem 48: Odd Even Jump (LeetCode 975)
 * 
 * From index i, odd jumps go to smallest value >= arr[i] to the right (smallest index if tie).
 * Even jumps go to largest value <= arr[i] to the right (smallest index if tie).
 * Count starting indices that can reach end.
 * 
 * Approach: Use monotonic stack on sorted indices to find next odd/even jumps.
 * Then DP from right.
 * 
 * Time: O(n log n), Space: O(n)
 * 
 * Production Analogy: State machine transitions where even/odd steps have
 * different routing rules.
 */
public class Problem48_OddEvenJump {
    
    public int oddEvenJumps(int[] arr) {
        int n = arr.length;
        int[] oddNext = new int[n], evenNext = new int[n];
        Arrays.fill(oddNext, -1);
        Arrays.fill(evenNext, -1);
        
        // Odd jump: next >= (smallest), sorted by value asc, index asc
        Integer[] indices = new Integer[n];
        for (int i = 0; i < n; i++) indices[i] = i;
        
        Arrays.sort(indices, (a, b) -> arr[a] != arr[b] ? arr[a] - arr[b] : a - b);
        Deque<Integer> stack = new ArrayDeque<>();
        for (int idx : indices) {
            while (!stack.isEmpty() && stack.peek() < idx) {
                oddNext[stack.pop()] = idx;
            }
            stack.push(idx);
        }
        
        // Even jump: next <= (largest), sorted by value desc, index asc
        Arrays.sort(indices, (a, b) -> arr[a] != arr[b] ? arr[b] - arr[a] : a - b);
        stack.clear();
        for (int idx : indices) {
            while (!stack.isEmpty() && stack.peek() < idx) {
                evenNext[stack.pop()] = idx;
            }
            stack.push(idx);
        }
        
        // DP
        boolean[] odd = new boolean[n], even = new boolean[n];
        odd[n-1] = even[n-1] = true;
        int count = 1;
        
        for (int i = n - 2; i >= 0; i--) {
            if (oddNext[i] != -1) odd[i] = even[oddNext[i]];
            if (evenNext[i] != -1) even[i] = odd[evenNext[i]];
            if (odd[i]) count++;
        }
        return count;
    }
    
    public static void main(String[] args) {
        Problem48_OddEvenJump sol = new Problem48_OddEvenJump();
        
        System.out.println(sol.oddEvenJumps(new int[]{10,13,12,14,15})); // 2
        System.out.println(sol.oddEvenJumps(new int[]{2,3,1,1,4}));     // 3
        System.out.println(sol.oddEvenJumps(new int[]{5,1,3,4,2}));     // 3
    }
}
