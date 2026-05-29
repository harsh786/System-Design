import java.util.*;

public class Problem14_SortThePeople {
    public static String[] sortPeople(String[] names, int[] heights) {
        // Counting sort since heights are bounded
        int max = 0; for (int h : heights) max = Math.max(max, h);
        String[] bucket = new String[max + 1];
        for (int i = 0; i < names.length; i++) bucket[heights[i]] = names[i];
        String[] result = new String[names.length];
        int idx = 0;
        for (int i = max; i >= 0; i--) if (bucket[i] != null) result[idx++] = bucket[i];
        return result;
    }

    public static void main(String[] args) {
        System.out.println(Arrays.toString(sortPeople(
            new String[]{"Mary","John","Emma"}, new int[]{180,165,170})));
    }
}
