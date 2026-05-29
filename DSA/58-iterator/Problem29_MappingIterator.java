import java.util.*;
import java.util.function.Function;

public class Problem29_MappingIterator<T, R> implements Iterator<R> {
    Iterator<T> source;
    Function<T, R> mapper;

    public Problem29_MappingIterator(Iterator<T> source, Function<T, R> mapper) {
        this.source = source; this.mapper = mapper;
    }

    public boolean hasNext() { return source.hasNext(); }
    public R next() { return mapper.apply(source.next()); }

    public static void main(String[] args) {
        Problem29_MappingIterator<Integer, String> it = new Problem29_MappingIterator<>(
            Arrays.asList(1,2,3,4,5).iterator(), n -> "item_" + n);
        while (it.hasNext()) System.out.print(it.next() + " ");
        System.out.println();
    }
}
