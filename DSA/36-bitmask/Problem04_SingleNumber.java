public class Problem04_SingleNumber {
    public int singleNumber(int[] nums) {
        int result = 0;
        for (int n : nums) result ^= n;
        return result;
    }

    public static void main(String[] args) {
        System.out.println(new Problem04_SingleNumber().singleNumber(new int[]{4,1,2,1,2})); // 4
    }
}
