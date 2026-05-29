import java.util.*;

public class Problem31_RandomizedTestCaseGenerator {
    static Random rand = new Random();

    public static int[] randomArray(int n, int min, int max) {
        int[] arr = new int[n];
        for (int i = 0; i < n; i++) arr[i] = min + rand.nextInt(max - min + 1);
        return arr;
    }

    public static int[][] randomGraph(int nodes, int edges) {
        Set<Long> used = new HashSet<>();
        List<int[]> result = new ArrayList<>();
        while (result.size() < edges) {
            int u = rand.nextInt(nodes), v = rand.nextInt(nodes);
            if (u != v && used.add((long)u * nodes + v)) result.add(new int[]{u, v});
        }
        return result.toArray(new int[0][]);
    }

    public static String randomString(int len, int charRange) {
        StringBuilder sb = new StringBuilder();
        for (int i = 0; i < len; i++) sb.append((char)('a' + rand.nextInt(charRange)));
        return sb.toString();
    }

    public static void main(String[] args) {
        System.out.println("Array: " + Arrays.toString(randomArray(10, -5, 5)));
        System.out.println("String: " + randomString(15, 5));
        int[][] g = randomGraph(5, 6);
        for (int[] e : g) System.out.println(Arrays.toString(e));
    }
}
