import java.util.*;

public class Problem04_ZigzagIterator {
    Queue<Iterator<Integer>> queue = new LinkedList<>();

    public Problem04_ZigzagIterator(List<Integer> v1, List<Integer> v2) {
        if (!v1.isEmpty()) queue.offer(v1.iterator());
        if (!v2.isEmpty()) queue.offer(v2.iterator());
    }

    public int next() {
        Iterator<Integer> it = queue.poll();
        int val = it.next();
        if (it.hasNext()) queue.offer(it);
        return val;
    }

    public boolean hasNext() { return !queue.isEmpty(); }

    public static void main(String[] args) {
        Problem04_ZigzagIterator it = new Problem04_ZigzagIterator(
            Arrays.asList(1,2), Arrays.asList(3,4,5,6));
        while (it.hasNext()) System.out.print(it.next() + " ");
        System.out.println(); // 1 3 2 4 5 6
    }
}
