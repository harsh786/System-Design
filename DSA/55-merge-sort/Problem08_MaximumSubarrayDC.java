public class Problem08_MaximumSubarrayDC {
    static int maxSubArray(int[] nums) { return solve(nums, 0, nums.length - 1); }
    
    static int solve(int[] a, int lo, int hi) {
        if (lo == hi) return a[lo];
        int mid = (lo + hi) / 2;
        int left = solve(a, lo, mid), right = solve(a, mid + 1, hi);
        int cross = crossMax(a, lo, mid, hi);
        return Math.max(Math.max(left, right), cross);
    }
    
    static int crossMax(int[] a, int lo, int mid, int hi) {
        int leftMax = Integer.MIN_VALUE, sum = 0;
        for (int i = mid; i >= lo; i--) { sum += a[i]; leftMax = Math.max(leftMax, sum); }
        int rightMax = Integer.MIN_VALUE; sum = 0;
        for (int i = mid + 1; i <= hi; i++) { sum += a[i]; rightMax = Math.max(rightMax, sum); }
        return leftMax + rightMax;
    }
    
    public static void main(String[] args) {
        System.out.println(maxSubArray(new int[]{-2, 1, -3, 4, -1, 2, 1, -5, 4})); // 6
    }
}
