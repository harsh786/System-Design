import java.util.*;

public class Problem32_InterpolationSearchWithOracle {
    static int[] arr = {10,20,30,40,50,60,70,80,90,100};
    static int query(int i) { return arr[i]; }
    
    static int interpolationSearch(int n, int target) {
        int lo = 0, hi = n - 1;
        while (lo <= hi && target >= query(lo) && target <= query(hi)) {
            int pos = lo + (int)((long)(target - query(lo)) * (hi - lo) / (query(hi) - query(lo)));
            int val = query(pos);
            if (val == target) return pos;
            else if (val < target) lo = pos + 1;
            else hi = pos - 1;
        }
        return -1;
    }
    
    public static void main(String[] args) {
        System.out.println("Search 70: " + interpolationSearch(10, 70)); // 6
    }
}
