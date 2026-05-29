import java.util.*;

public class Problem50_CompositeIteratorPattern implements Iterator<Integer> {
    // Compose multiple iterator transformations
    Iterator<Integer> inner;

    public Problem50_CompositeIteratorPattern(Iterator<Integer> source,
            java.util.function.Predicate<Integer> filter,
            java.util.function.Function<Integer, Integer> mapper) {
        List<Integer> result = new ArrayList<>();
        while (source.hasNext()) {
            int val = source.next();
            if (filter.test(val)) result.add(mapper.apply(val));
        }
        inner = result.iterator();
    }

    public boolean hasNext() { return inner.hasNext(); }
    public Integer next() { return inner.next(); }

    public static void main(String[] args) {
        // Filter evens, then square them
        Problem50_CompositeIteratorPattern it = new Problem50_CompositeIteratorPattern(
            Arrays.asList(1,2,3,4,5,6,7,8,9,10).iterator(),
            n -> n % 2 == 0,
            n -> n * n);
        while (it.hasNext()) System.out.print(it.next() + " ");
        System.out.println(); // 4 16 36 64 100
    }
}
