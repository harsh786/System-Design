import java.util.*;

public class Problem36_QueryLimitedSortedSearch {
    static int[] arr = {1,3,5,7,9,11,13,15,17,19,21,23,25};
    static int queryBudget = 4;
    static int queriesUsed = 0;
    
    static int query(int i) { queriesUsed++; return arr[i]; }
    
    static int search(int n, int target) {
        int lo = 0, hi = n - 1;
        while (lo <= hi && queriesUsed < queryBudget) {
            int mid = lo + (hi - lo) / 2;
            int v = query(mid);
            if (v == target) return mid;
            else if (v < target) lo = mid + 1;
            else hi = mid - 1;
        }
        return -1;
    }
    
    public static void main(String[] args) {
        System.out.println("Search 7 (budget=4): " + search(arr.length, 7) + " queries=" + queriesUsed);
    }
}
