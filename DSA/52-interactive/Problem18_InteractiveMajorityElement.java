import java.util.*;

public class Problem18_InteractiveMajorityElement {
    static int[] arr = {3, 3, 4, 2, 3, 3, 3};
    static int query(int i) { return arr[i]; }
    
    static int findMajority(int n) {
        int candidate = query(0), count = 1;
        for (int i = 1; i < n; i++) {
            int val = query(i);
            if (count == 0) { candidate = val; count = 1; }
            else count += (val == candidate) ? 1 : -1;
        }
        return candidate;
    }
    
    public static void main(String[] args) {
        System.out.println("Majority: " + findMajority(arr.length)); // 3
    }
}
