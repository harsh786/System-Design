import java.util.*;

public class Problem27_DLLFreeListAllocator {
    static class Block{int start,size;Block prev,next;Block(int s,int sz){start=s;size=sz;}}
    Block head=new Block(-1,0),tail=new Block(-1,0);
    
    Problem27_DLLFreeListAllocator(int totalSize){
        head.next=tail;tail.prev=head;
        Block b=new Block(0,totalSize);b.prev=head;b.next=tail;head.next=b;tail.prev=b;
    }
    
    int allocate(int size){
        Block cur=head.next;
        while(cur!=tail){
            if(cur.size>=size){int addr=cur.start;cur.start+=size;cur.size-=size;
                if(cur.size==0){cur.prev.next=cur.next;cur.next.prev=cur.prev;}
                return addr;}
            cur=cur.next;
        }
        return -1;
    }
    
    void free(int start,int size){
        Block b=new Block(start,size);
        Block cur=head.next;
        while(cur!=tail&&cur.start<start)cur=cur.next;
        b.next=cur;b.prev=cur.prev;cur.prev.next=b;cur.prev=b;
        // Coalesce with next/prev
        if(b.next!=tail&&b.start+b.size==b.next.start){b.size+=b.next.size;b.next=b.next.next;b.next.prev=b;}
        if(b.prev!=head&&b.prev.start+b.prev.size==b.start){b.prev.size+=b.size;b.prev.next=b.next;b.next.prev=b.prev;}
    }
    
    public static void main(String[] args) {
        Problem27_DLLFreeListAllocator a=new Problem27_DLLFreeListAllocator(100);
        System.out.println("Alloc 20: "+a.allocate(20)); // 0
        System.out.println("Alloc 30: "+a.allocate(30)); // 20
        a.free(0,20);
        System.out.println("Alloc 15: "+a.allocate(15)); // 0
    }
}
