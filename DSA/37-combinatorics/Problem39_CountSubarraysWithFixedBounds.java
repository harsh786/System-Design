public class Problem39_CountSubarraysWithFixedBounds {
    public long countSubarrays(int[] nums, int minK, int maxK) {
        long result = 0;
        int lastMin = -1, lastMax = -1, lastBad = -1;
        for (int i = 0; i < nums.length; i++) {
            if (nums[i] < minK || nums[i] > maxK) lastBad = i;
            if (nums[i] == minK) lastMin = i;
            if (nums[i] == maxK) lastMax = i;
            result += Math.max(0, Math.min(lastMin, lastMax) - lastBad);
        }
        return result;
    }

    public static void main(String[] args) {
        System.out.println(new Problem39_CountSubarraysWithFixedBounds().countSubarrays(new int[]{1,3,5,2,7,5}, 1, 5));
    }
}
