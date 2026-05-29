public class Problem32_FairDistributionOfCookies {
    int ans = Integer.MAX_VALUE;

    public int distributeCookies(int[] cookies, int k) {
        backtrack(cookies, new int[k], 0);
        return ans;
    }

    private void backtrack(int[] cookies, int[] children, int idx) {
        if (idx == cookies.length) { int max = 0; for (int c : children) max = Math.max(max, c); ans = Math.min(ans, max); return; }
        for (int i = 0; i < children.length; i++) {
            children[i] += cookies[idx];
            if (children[i] < ans) backtrack(cookies, children, idx + 1);
            children[i] -= cookies[idx];
            if (children[i] == 0) break; // pruning
        }
    }

    public static void main(String[] args) {
        System.out.println(new Problem32_FairDistributionOfCookies().distributeCookies(new int[]{8,15,10,20,8}, 2));
    }
}
