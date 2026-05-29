import java.util.*;

public class Problem34_SubsetsIterator implements Iterator<List<Integer>> {
    int[] nums;
    int mask, total;

    public Problem34_SubsetsIterator(int[] nums) { this.nums = nums; mask = 0; total = 1 << nums.length; }

    public boolean hasNext() { return mask < total; }

    public List<Integer> next() {
        List<Integer> subset = new ArrayList<>();
        for (int i = 0; i < nums.length; i++) if ((mask & (1<<i)) != 0) subset.add(nums[i]);
        mask++;
        return subset;
    }

    public static void main(String[] args) {
        Problem34_SubsetsIterator it = new Problem34_SubsetsIterator(new int[]{1,2,3});
        while (it.hasNext()) System.out.println(it.next());
    }
}
