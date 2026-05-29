import java.util.*;

public class Problem22_ChunkedStreamIterator implements Iterator<Integer> {
    Iterator<List<Integer>> chunkIter;
    Iterator<Integer> currentChunk;

    public Problem22_ChunkedStreamIterator(Iterator<List<Integer>> chunks) {
        chunkIter = chunks; advance();
    }

    void advance() { currentChunk = chunkIter.hasNext() ? chunkIter.next().iterator() : Collections.emptyIterator(); }

    public boolean hasNext() {
        while (!currentChunk.hasNext() && chunkIter.hasNext()) advance();
        return currentChunk.hasNext();
    }

    public Integer next() { return currentChunk.next(); }

    public static void main(String[] args) {
        List<List<Integer>> chunks = Arrays.asList(Arrays.asList(1,2), Arrays.asList(), Arrays.asList(3,4,5));
        Problem22_ChunkedStreamIterator it = new Problem22_ChunkedStreamIterator(chunks.iterator());
        while (it.hasNext()) System.out.print(it.next() + " ");
        System.out.println();
    }
}
