import java.util.*;

/**
 * Problem 10: Shell Sort Performance Benchmarks
 * 
 * Comprehensive benchmarks comparing Shell Sort variants against each other
 * and against Arrays.sort (dual-pivot quicksort) on different data distributions:
 * - Random
 * - Sorted
 * - Reverse sorted
 * - Few unique values
 * - Sawtooth pattern
 */
public class Problem10_ShellSortBenchmarks {

    interface SortAlgorithm {
        void sort(int[] arr);
    }

    static SortAlgorithm knuthShellSort = arr -> {
        int n = arr.length, gap = 1;
        while (gap < n/3) gap = 3*gap + 1;
        while (gap >= 1) {
            for (int i = gap; i < n; i++) {
                int t = arr[i]; int j = i;
                while (j >= gap && arr[j-gap] > t) { arr[j] = arr[j-gap]; j -= gap; }
                arr[j] = t;
            }
            gap /= 3;
        }
    };

    static SortAlgorithm ciuraShellSort = arr -> {
        int[] gaps = {701, 301, 132, 57, 23, 10, 4, 1};
        int n = arr.length;
        for (int gap : gaps) {
            if (gap >= n) continue;
            for (int i = gap; i < n; i++) {
                int t = arr[i]; int j = i;
                while (j >= gap && arr[j-gap] > t) { arr[j] = arr[j-gap]; j -= gap; }
                arr[j] = t;
            }
        }
    };

    static SortAlgorithm javaSort = Arrays::sort;

    static int[] generateData(String type, int n, Random rand) {
        int[] arr = new int[n];
        switch (type) {
            case "random":
                for (int i = 0; i < n; i++) arr[i] = rand.nextInt(n * 10);
                break;
            case "sorted":
                for (int i = 0; i < n; i++) arr[i] = i;
                break;
            case "reverse":
                for (int i = 0; i < n; i++) arr[i] = n - i;
                break;
            case "fewUnique":
                for (int i = 0; i < n; i++) arr[i] = rand.nextInt(10);
                break;
            case "sawtooth":
                for (int i = 0; i < n; i++) arr[i] = i % (n / 10);
                break;
        }
        return arr;
    }

    static long benchmark(SortAlgorithm algo, int[] data, int trials) {
        long total = 0;
        for (int t = 0; t < trials; t++) {
            int[] arr = data.clone();
            long start = System.nanoTime();
            algo.sort(arr);
            total += System.nanoTime() - start;
        }
        return total / trials;
    }

    public static void main(String[] args) {
        int n = 50000;
        int trials = 5;
        Random rand = new Random(42);
        String[] distributions = {"random", "sorted", "reverse", "fewUnique", "sawtooth"};
        String[] algoNames = {"Knuth Shell", "Ciura Shell", "Arrays.sort"};
        SortAlgorithm[] algos = {knuthShellSort, ciuraShellSort, javaSort};

        System.out.printf("Benchmark: n=%d, %d trials each%n%n", n, trials);
        System.out.printf("%-12s", "Distribution");
        for (String name : algoNames) System.out.printf("%-15s", name);
        System.out.println();
        System.out.println("-".repeat(57));

        for (String dist : distributions) {
            int[] data = generateData(dist, n, rand);
            System.out.printf("%-12s", dist);
            for (SortAlgorithm algo : algos) {
                long time = benchmark(algo, data, trials);
                System.out.printf("%-15s", String.format("%.2f ms", time / 1e6));
            }
            System.out.println();
        }

        System.out.println("\nConclusions:");
        System.out.println("- Shell Sort is competitive for medium-sized arrays");
        System.out.println("- Arrays.sort (quicksort) wins on large random data");
        System.out.println("- Shell Sort excels on nearly sorted / small data");
        System.out.println("- No extra memory needed (unlike merge sort)");
    }
}
