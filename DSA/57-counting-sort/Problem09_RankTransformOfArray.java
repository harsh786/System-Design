import java.util.*;

public class Problem09_RankTransformOfArray {
    public static int[] arrayRankTransform(int[] arr) {
        int[] sorted = arr.clone();
        Arrays.sort(sorted);
        Map<Integer, Integer> rank = new HashMap<>();
        for (int n : sorted) rank.putIfAbsent(n, rank.size() + 1);
        int[] result = new int[arr.length];
        for (int i = 0; i < arr.length; i++) result[i] = rank.get(arr[i]);
        return result;
    }

    public static void main(String[] args) {
        System.out.println(Arrays.toString(arrayRankTransform(new int[]{40,10,20,30})));
        // [4,1,2,3]
    }
}
