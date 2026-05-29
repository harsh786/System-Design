import java.util.*;

public class Problem25_InterleavingIterator implements Iterator<Integer> {
    List<Iterator<Integer>> iters = new ArrayList<>();
    int current = 0;

    public Problem25_InterleavingIterator(List<Iterator<Integer>> iterators) {
        for (Iterator<Integer> it : iterators) if (it.hasNext()) iters.add(it);
    }

    public boolean hasNext() { return !iters.isEmpty(); }

    public Integer next() {
        if (current >= iters.size()) current = 0;
        Iterator<Integer> it = iters.get(current);
        int val = it.next();
        if (!it.hasNext()) iters.remove(current);
        else current++;
        if (current >= iters.size()) current = 0;
        return val;
    }

    public static void main(String[] args) {
        Problem25_InterleavingIterator it = new Problem25_InterleavingIterator(Arrays.asList(
            Arrays.asList(1,2,3).iterator(), Arrays.asList(4,5).iterator(), Arrays.asList(6,7,8,9).iterator()));
        while (it.hasNext()) System.out.print(it.next() + " ");
        System.out.println();
    }
}
