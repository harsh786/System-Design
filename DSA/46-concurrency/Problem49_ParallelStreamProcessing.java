import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.locks.*;
import java.util.concurrent.atomic.*;
import java.util.stream.*;

public class Problem49_ParallelStreamProcessing {
    /**
     * Problem: Parallel Stream Processing
     * Process large dataset using parallel streams with proper reduction.
     * Time: O(n/p) with p processors | Space: O(n)
     * Production Analogy: Batch data transformation (ETL) leveraging multi-core.
     */
    public static void main(String[] args) {
        List<Integer> data = IntStream.rangeClosed(1, 1_000_000).boxed().collect(Collectors.toList());

        // Parallel sum
        long sum = data.parallelStream().mapToLong(Integer::longValue).sum();
        System.out.println("Parallel sum: " + sum);

        // Parallel filter + map
        long count = data.parallelStream().filter(x -> x % 7 == 0).mapToLong(x -> x * 2L).count();
        System.out.println("Multiples of 7: " + count);

        // Custom parallel reduction
        long product = data.parallelStream().limit(10).reduce(1, (a, b) -> a * b, (a, b) -> a * b);
        System.out.println("Product of first 10: " + product);

        // GroupBy parallel
        Map<Integer, List<Integer>> grouped = data.parallelStream().limit(20).collect(Collectors.groupingBy(x -> x % 4));
        System.out.println("Grouped by mod 4: " + grouped);
    }
}
