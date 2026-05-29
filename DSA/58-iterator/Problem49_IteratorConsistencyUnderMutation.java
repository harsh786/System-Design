import java.util.*;

public class Problem49_IteratorConsistencyUnderMutation {
    // Snapshot iterator: takes a snapshot at creation time
    static class SnapshotIterator<T> implements Iterator<T> {
        List<T> snapshot;
        int idx = 0;
        SnapshotIterator(List<T> list) { snapshot = new ArrayList<>(list); }
        public boolean hasNext() { return idx < snapshot.size(); }
        public T next() { return snapshot.get(idx++); }
    }

    public static void main(String[] args) {
        List<Integer> list = new ArrayList<>(Arrays.asList(1,2,3,4,5));
        SnapshotIterator<Integer> it = new SnapshotIterator<>(list);
        list.add(6); list.remove(0); // mutate original
        System.out.print("Snapshot (unchanged): ");
        while (it.hasNext()) System.out.print(it.next() + " ");
        System.out.println();
        System.out.println("Original (mutated): " + list);
    }
}
