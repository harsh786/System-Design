public class Problem24_DLLPlaylist {
    static class Song{String name;Song prev,next;Song(String n){name=n;}}
    Song head,tail,current;
    
    void add(String name){
        Song s=new Song(name);
        if(head==null){head=tail=current=s;}
        else{tail.next=s;s.prev=tail;tail=s;}
    }
    String playNext(){if(current!=null&&current.next!=null)current=current.next;return current!=null?current.name:null;}
    String playPrev(){if(current!=null&&current.prev!=null)current=current.prev;return current!=null?current.name:null;}
    String nowPlaying(){return current!=null?current.name:null;}
    
    public static void main(String[] args) {
        Problem24_DLLPlaylist p=new Problem24_DLLPlaylist();
        p.add("Song1");p.add("Song2");p.add("Song3");
        System.out.println("Now: "+p.nowPlaying());
        System.out.println("Next: "+p.playNext());
        System.out.println("Next: "+p.playNext());
        System.out.println("Prev: "+p.playPrev());
    }
}
