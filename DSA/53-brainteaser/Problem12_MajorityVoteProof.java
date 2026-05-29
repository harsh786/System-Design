public class Problem12_MajorityVoteProof {
    // Boyer-Moore Voting: if majority exists, it survives cancellation
    static int majorityElement(int[] nums) {
        int cand = 0, count = 0;
        for (int n : nums) {
            if (count == 0) cand = n;
            count += (n == cand) ? 1 : -1;
        }
        // Verify
        int c = 0; for (int n : nums) if (n == cand) c++;
        return c > nums.length / 2 ? cand : -1;
    }
    
    public static void main(String[] args) {
        System.out.println(majorityElement(new int[]{2,2,1,1,1,2,2})); // 2
    }
}
