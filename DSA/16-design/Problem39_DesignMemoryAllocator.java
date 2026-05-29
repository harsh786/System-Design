import java.util.*;

/**
 * Problem 39: Design Memory Allocator
 * 
 * API Contract:
 * - allocate(size, mID): Allocate `size` consecutive free units to mID. Return start index or -1.
 * - free(mID): Free all units allocated to mID. Return total freed units.
 * 
 * Complexity: allocate O(n), free O(n) where n = memory size
 * Data Structure: Array representing memory blocks
 * 
 * Production Analogy: malloc/free implementation, disk block allocation,
 * GPU memory management, slab allocators in Linux kernel
 */
public class Problem39_DesignMemoryAllocator {

    static class Allocator {
        private int[] memory;

        public Allocator(int n) { memory = new int[n]; }

        public int allocate(int size, int mID) {
            int count = 0;
            for (int i = 0; i < memory.length; i++) {
                if (memory[i] == 0) {
                    count++;
                    if (count == size) {
                        // Fill from i-size+1 to i
                        for (int j = i - size + 1; j <= i; j++) memory[j] = mID;
                        return i - size + 1;
                    }
                } else {
                    count = 0;
                }
            }
            return -1;
        }

        public int free(int mID) {
            int freed = 0;
            for (int i = 0; i < memory.length; i++) {
                if (memory[i] == mID) { memory[i] = 0; freed++; }
            }
            return freed;
        }
    }

    public static void main(String[] args) {
        Allocator alloc = new Allocator(10);
        assert alloc.allocate(1, 1) == 0;
        assert alloc.allocate(1, 2) == 1;
        assert alloc.allocate(1, 3) == 2;
        assert alloc.free(2) == 1;
        assert alloc.allocate(3, 4) == 3; // slot 1 free but need 3 consecutive
        assert alloc.allocate(1, 1) == 1; // reuse freed slot
        assert alloc.free(1) == 2; // frees index 0 and 1
        assert alloc.allocate(10, 5) == -1; // not enough space

        System.out.println("All tests passed!");
    }
}
