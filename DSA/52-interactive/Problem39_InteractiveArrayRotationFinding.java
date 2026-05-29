import java.util.*;

public class Problem39_InteractiveArrayRotationFinding {
    static int[] arr = {4, 5, 6, 7, 0, 1, 2};
    static int query(int i) { return arr[i]; }
    
    static int findRotation(int n) {
        int lo = 0, hi = n - 1;
        while (lo < hi) {
            int mid = lo + (hi - lo) / 2;
            if (query(mid) > query(hi)) lo = mid + 1;
            else hi = mid;
        }
        return lo;
    }
    
    public static void main(String[] args) {
        System.out.println("Rotation point: " + findRotation(arr.length)); // 4
    }
}
