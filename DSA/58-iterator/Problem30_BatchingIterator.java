import java.util.*;

public class Problem30_BatchingIterator implements Iterator<List<Integer>> {
    Iterator<Integer> source;
    int batchSize;

    public Problem30_BatchingIterator(Iterator<Integer> source, int batchSize) {
        this.source = source; this.batchSize = batchSize;
    }

    public boolean hasNext() { return source.hasNext(); }

    public List<Integer> next() {
        List<Integer> batch = new ArrayList<>();
        for (int i = 0; i < batchSize && source.hasNext(); i++) batch.add(source.next());
        return batch;
    }

    public static void main(String[] args) {
        Problem30_BatchingIterator it = new Problem30_BatchingIterator(
            Arrays.asList(1,2,3,4,5,6,7).iterator(), 3);
        while (it.hasNext()) System.out.println(it.next());
    }
}
