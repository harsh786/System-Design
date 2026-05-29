import java.util.*;

public class Problem11_FindHiddenArraySumQueries {
    static int[] hidden = {3, 1, 4, 1, 5};
    
    static int querySum(int l, int r) {
        int s = 0; for (int i = l; i <= r; i++) s += hidden[i]; return s;
    }
    
    static int[] recover(int n) {
        int[] result = new int[n];
        int total = querySum(0, n - 1);
        // Query each prefix sum
        int prev = 0;
        for (int i = 0; i < n; i++) {
            int prefixSum = querySum(0, i);
            result[i] = prefixSum - prev;
            prev = prefixSum;
        }
        return result;
    }
    
    public static void main(String[] args) {
        System.out.println(Arrays.toString(recover(5)));
    }
}
