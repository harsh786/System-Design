import java.util.*;

/**
 * Problem 43: Process Restricted Friend Requests (LeetCode 2076)
 * 
 * n people, restrictions (can't be in same group), and friend requests.
 * Process each request: approve if it doesn't violate any restriction.
 * 
 * Approach: For each request, tentatively check if unioning would violate
 * any restriction (any pair in restrictions would end up in same component).
 * 
 * Time: O(Q * R * α(n)), Space: O(n)
 * 
 * Production Analogy: Access control group merging - merge user groups only if
 * no conflicting permission boundaries are violated.
 */
public class Problem43_ProcessRestrictedFriendRequests {
    
    int[] parent, rank;
    
    public boolean[] friendRequests(int n, int[][] restrictions, int[][] requests) {
        parent = new int[n]; rank = new int[n];
        for (int i = 0; i < n; i++) parent[i] = i;
        
        boolean[] result = new boolean[requests.length];
        for (int i = 0; i < requests.length; i++) {
            int pu = find(requests[i][0]), pv = find(requests[i][1]);
            if (pu == pv) { result[i] = true; continue; }
            
            boolean valid = true;
            for (int[] r : restrictions) {
                int pr0 = find(r[0]), pr1 = find(r[1]);
                if ((pr0 == pu && pr1 == pv) || (pr0 == pv && pr1 == pu)) {
                    valid = false; break;
                }
            }
            if (valid) {
                union(pu, pv);
                result[i] = true;
            }
        }
        return result;
    }
    
    private int find(int x) {
        if (parent[x] != x) parent[x] = find(parent[x]);
        return parent[x];
    }
    
    private void union(int x, int y) {
        int px = find(x), py = find(y);
        if (px == py) return;
        if (rank[px] < rank[py]) parent[px] = py;
        else if (rank[px] > rank[py]) parent[py] = px;
        else { parent[py] = px; rank[px]++; }
    }
    
    public static void main(String[] args) {
        Problem43_ProcessRestrictedFriendRequests sol = new Problem43_ProcessRestrictedFriendRequests();
        System.out.println(Arrays.toString(sol.friendRequests(3,
            new int[][]{{0,1}}, new int[][]{{0,2},{2,1}}))); // [true, false]
        
        sol = new Problem43_ProcessRestrictedFriendRequests();
        System.out.println(Arrays.toString(sol.friendRequests(5,
            new int[][]{{0,1},{1,2},{2,3}}, new int[][]{{0,4},{1,2},{3,1},{3,4}}))); // [true,false,true,false]
    }
}
